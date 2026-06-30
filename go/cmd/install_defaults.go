package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
	"github.com/r14r/ollama-cli/internal/config"
)

var installDefaultsCmd = &cobra.Command{
	Use:   "install-defaults",
	Short: "Pull default model set into the Ollama volume",
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := compose.EnsureServiceRunning(); err != nil {
			return err
		}

		defaultModels := config.GetDefaultModels()
		fmt.Printf("Pulling default models into Ollama volume for service '%s'...\n", compose.SERVICE)
		fmt.Println("Models:")
		for _, m := range defaultModels {
			fmt.Printf("  %s\n", m)
		}
		fmt.Println()

		for _, model := range defaultModels {
			fmt.Printf("==> ollama pull %s\n", model)
			if err := compose.ComposeExec([]string{"ollama", "pull", model}); err != nil {
				return err
			}
			fmt.Println()
		}

		fmt.Println("Done. Current tags:")
		compose.ComposeExec([]string{"ollama", "list"})
		return nil
	},
}
