package cmd

import (
	"fmt"
	"strings"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
)

var versionCmd = &cobra.Command{
	Use:   "version",
	Short: "Show ollama (container) and ollama-cli versions",
	RunE: func(cmd *cobra.Command, args []string) error {
		out, err := compose.ComposeExecCapture([]string{"ollama", "--version"})
		if err != nil {
			return err
		}
		fmt.Printf("ollama version: %s\n", lastField(out))
		fmt.Printf("ollama-cli version: %s\n", AppVersion)
		return nil
	},
}

// lastField returns the last whitespace-separated field, e.g. turns
// "ollama version is 0.32.15" into "0.32.15".
func lastField(s string) string {
	fields := strings.Fields(s)
	if len(fields) == 0 {
		return strings.TrimSpace(s)
	}
	return fields[len(fields)-1]
}
