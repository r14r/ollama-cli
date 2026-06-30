package cmd

import (
	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
)

var downCmd = &cobra.Command{
	Use:   "down",
	Short: "Stop the Ollama service stack",
	RunE: func(cmd *cobra.Command, args []string) error {
		return compose.RunCmd(compose.BuildComposeCmd("down"))
	},
}
