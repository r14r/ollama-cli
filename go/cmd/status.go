package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
)

var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show container and model status",
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := compose.EnsureComposeFile(); err != nil {
			return err
		}

		fmt.Printf("Compose file : %s\n", compose.GetComposeFile())
		fmt.Printf("Project name : %s\n", compose.PROJECT_NAME)
		fmt.Printf("Service      : %s\n", compose.SERVICE)
		fmt.Println()

		fmt.Println("Container status:")
		compose.RunCmd(compose.BuildComposeCmd("ps", compose.SERVICE))
		fmt.Println()

		running, _ := compose.IsServiceRunning()
		if running {
			fmt.Println("Ollama models:")
			compose.ComposeExec([]string{"ollama", "list"})
			fmt.Println()
			fmt.Println("Running models:")
			compose.ComposeExec([]string{"ollama", "ps"})
		} else {
			fmt.Printf("Service '%s' is not running.\n", compose.SERVICE)
		}
		return nil
	},
}
