package cmd

import (
	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
)

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Show Ollama version inside the container",
	RunE: func(cmd *cobra.Command, args []string) error {
		return compose.ComposeExec([]string{"ollama", "--version"})
	},
}
