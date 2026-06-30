package cmd

import (
	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
)

var buildCmd = &cobra.Command{
	Use:   "build",
	Short: "Pull base image and rebuild the Ollama service",
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := compose.RunCmd([]string{"docker", "pull", "ollama/ollama:latest"}); err != nil {
			return err
		}
		return compose.RunCmd(compose.BuildComposeCmd("build"))
	},
}
