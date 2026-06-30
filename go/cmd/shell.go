package cmd

import (
	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
)

var shellCmd = &cobra.Command{
	Use:   "shell",
	Short: "Open a shell inside the Ollama container",
	RunE: func(cmd *cobra.Command, args []string) error {
		return compose.ComposeExec([]string{"bash"})
	},
}
