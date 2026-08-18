package cmd

import (
	"fmt"
	"os"
	"os/exec"
	"strings"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
)

// AppVersion can be overridden at build time via -ldflags "-X github.com/r14r/ollama-cli/cmd.AppVersion=x.y.z"
var AppVersion = "dev"

var rootCmd = &cobra.Command{
	Use:   "ollama-cli",
	Short: "Ollama CLI wrapper",
	Long:  "Extended Ollama CLI helper and Docker Compose wrapper.",
	RunE:  handleUnknownCommand,
}

func init() {
	rootCmd.PersistentFlags().BoolP("debug", "", false, "Enable debug log output")
	rootCmd.Version = AppVersion

	// Add subcommands
	rootCmd.AddCommand(upCmd)
	rootCmd.AddCommand(downCmd)
	rootCmd.AddCommand(buildCmd)
	rootCmd.AddCommand(statusCmd)
	rootCmd.AddCommand(versionCmd)
	rootCmd.AddCommand(shellCmd)
	rootCmd.AddCommand(profilesCmd)
	rootCmd.AddCommand(installDefaultsCmd)
	rootCmd.AddCommand(installModelsCmd)
	rootCmd.AddCommand(setupCmd)
	rootCmd.AddCommand(updateModelsCmd)
	rootCmd.AddCommand(launchCmd)
	rootCmd.AddCommand(listCmd)
	rootCmd.AddCommand(lsCmd)
	rootCmd.AddCommand(listRemoteCmd)
	rootCmd.AddCommand(blobsCmd)
	rootCmd.AddCommand(modelsCmd)
	rootCmd.AddCommand(helpCmd)
}

func handleUnknownCommand(cmd *cobra.Command, args []string) error {
	if len(args) > 0 {
		debugPrint(fmt.Sprintf("unrecognized command '%s', proxying to container", args[0]))
		return proxyToOllama(args)
	}
	cmd.Help()
	return nil
}

func proxyToOllama(args []string) error {
	filtered := []string{}
	for _, arg := range args {
		if arg != "--debug" {
			filtered = append(filtered, arg)
		}
	}

	composeCmd := compose.BuildComposeCmd("exec")
	if !compose.IsTTY() {
		composeCmd = append(composeCmd, "-T")
	}
	composeCmd = append(composeCmd, compose.SERVICE)
	composeCmd = append(composeCmd, "ollama")
	composeCmd = append(composeCmd, filtered...)

	debugPrint(fmt.Sprintf("executing: %s", strings.Join(composeCmd, " ")))

	cmd := exec.Command(composeCmd[0], composeCmd[1:]...)
	cmd.Stdout = os.Stdout
	cmd.Stderr = os.Stderr
	cmd.Stdin = os.Stdin
	return cmd.Run()
}

func Execute() error {
	if len(os.Args) > 1 {
		_, _, err := rootCmd.Find(os.Args[1:])
		if err != nil && strings.Contains(err.Error(), "unknown command") {
			return proxyToOllama(os.Args[1:])
		}
	}
	return rootCmd.Execute()
}

func debugPrint(msg string) {
	if os.Getenv("OLLAMA_DEBUG") != "" && os.Getenv("OLLAMA_DEBUG") != "0" && os.Getenv("OLLAMA_DEBUG") != "false" {
		fmt.Fprintf(os.Stderr, "DEBUG: %s\n", msg)
	}
}
