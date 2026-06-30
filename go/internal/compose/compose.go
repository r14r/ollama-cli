package compose

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
)

var (
	SERVICE     = os.Getenv("OLLAMA_COMPOSE_SERVICE")
	PROJECT_NAME = os.Getenv("OLLAMA_PROJECT_NAME")
)

func init() {
	if SERVICE == "" {
		SERVICE = "ollama"
	}
	if PROJECT_NAME == "" {
		PROJECT_NAME = "ai-tools-ollama"
	}
}

func ResolveComposeDir() string {
	// 1. OLLAMA_COMPOSE_DIR env
	if dir := os.Getenv("OLLAMA_COMPOSE_DIR"); dir != "" {
		return dir
	}

	// 2. ~/.ollama-cli/docker/
	home, _ := os.UserHomeDir()
	defaultDir := filepath.Join(home, ".ollama-cli", "docker")
	if fileExists(filepath.Join(defaultDir, "docker-compose.yaml")) {
		return defaultDir
	}

	// 3. Hardcoded dev path
	devPath := "/Users/Shared/CLOUD/Projekte/CLIs/ollama-cli/docker"
	if fileExists(filepath.Join(devPath, "docker-compose.yaml")) {
		return devPath
	}

	// 4. cwd fallback
	return "."
}

func GetComposeFile() string {
	return filepath.Join(ResolveComposeDir(), "docker-compose.yaml")
}

func BuildComposeCmd(args ...string) []string {
	composeFile := GetComposeFile()
	cmd := []string{"docker", "compose", "-p", PROJECT_NAME, "-f", composeFile}
	return append(cmd, args...)
}

func EnsureComposeFile() error {
	composeFile := GetComposeFile()
	if _, err := os.Stat(composeFile); err != nil {
		return fmt.Errorf("docker-compose.yaml not found at: %s", composeFile)
	}
	return nil
}

func IsTTY() bool {
	return isStdinTTY() && isStdoutTTY()
}

func isStdinTTY() bool {
	stat, _ := os.Stdin.Stat()
	return (stat.Mode() & os.ModeCharDevice) != 0
}

func isStdoutTTY() bool {
	stat, _ := os.Stdout.Stat()
	return (stat.Mode() & os.ModeCharDevice) != 0
}

func RunCmd(args []string) error {
	cmd := exec.Command(args[0], args[1:]...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	return cmd.Run()
}

func RunCmdCapture(args []string) (string, error) {
	cmd := exec.Command(args[0], args[1:]...)
	out, err := cmd.CombinedOutput()
	return string(out), err
}

func IsServiceRunning() (bool, error) {
	if err := EnsureComposeFile(); err != nil {
		return false, err
	}
	cmd := BuildComposeCmd("ps", "-q", SERVICE)
	out, err := RunCmdCapture(cmd)
	return strings.TrimSpace(out) != "", err
}

func EnsureServiceRunning() error {
	if err := EnsureComposeFile(); err != nil {
		return err
	}
	running, err := IsServiceRunning()
	if err != nil {
		return err
	}
	if !running {
		cmd := BuildComposeCmd("up", "-d", SERVICE)
		return RunCmd(cmd)
	}
	return nil
}

func ComposeExec(args []string) error {
	if err := EnsureServiceRunning(); err != nil {
		return err
	}
	cmd := BuildComposeCmd("exec")
	if !IsTTY() {
		cmd = append(cmd, "-T")
	}
	cmd = append(cmd, SERVICE)
	cmd = append(cmd, args...)
	return RunCmd(cmd)
}

func ComposeExecCapture(args []string) (string, error) {
	if err := EnsureServiceRunning(); err != nil {
		return "", err
	}
	cmd := BuildComposeCmd("exec")
	if !IsTTY() {
		cmd = append(cmd, "-T")
	}
	cmd = append(cmd, SERVICE)
	cmd = append(cmd, args...)
	return RunCmdCapture(cmd)
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}
