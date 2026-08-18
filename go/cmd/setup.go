package cmd

import (
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/config"
)

var setupCmd = &cobra.Command{
	Use:   "setup",
	Short: "Set up environment and default models",
	RunE: func(cmd *cobra.Command, args []string) error {
		home, _ := os.UserHomeDir()
		configDir := filepath.Join(home, ".ollama-cli")
		dockerDir := filepath.Join(configDir, "docker")
		configFile := filepath.Join(configDir, "setup.yml")

		if err := os.MkdirAll(dockerDir, 0755); err != nil {
			return err
		}

		if _, err := os.Stat(configFile); os.IsNotExist(err) {
			models := config.GetDefaultModels()
			modelsStr := ""
			for _, m := range models {
				modelsStr += fmt.Sprintf("    - %s\n", m)
			}
			content := fmt.Sprintf("ollama:\n  # List of default models to pull when running 'install-defaults'\n  default_models:\n%s", modelsStr)
			if err := os.WriteFile(configFile, []byte(content), 0644); err != nil {
				return err
			}
			fmt.Printf("Created setup file: %s\n", configFile)
		} else {
			fmt.Printf("Setup file already exists: %s\n", configFile)
		}

		fmt.Printf("Created docker directory: %s\n", dockerDir)

		edit, _ := cmd.Flags().GetBool("edit")
		if edit {
			editor := os.Getenv("EDITOR")
			var editCmd *exec.Cmd
			if editor != "" {
				editCmd = exec.Command(editor, configFile)
			} else if runtime.GOOS == "darwin" {
				editCmd = exec.Command("open", "-e", configFile)
			} else {
				editCmd = exec.Command("nano", configFile)
			}
			editCmd.Stdout = os.Stdout
			editCmd.Stderr = os.Stderr
			editCmd.Stdin = os.Stdin
			return editCmd.Run()
		}
		return nil
	},
}

func init() {
	setupCmd.Flags().BoolP("edit", "", false, "Edit the setup.yml file using your default editor")
}
