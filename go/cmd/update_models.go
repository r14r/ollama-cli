package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
	"github.com/r14r/ollama-cli/internal/models"
)

var updateModelsCmd = &cobra.Command{
	Use:   "update-models",
	Short: "Pull the latest version for all installed models",
	RunE: func(cmd *cobra.Command, args []string) error {
		installed := models.GetInstalledModels()
		for _, model := range installed {
			fmt.Printf("Update '%s'\n", model)
			if err := compose.ComposeExec([]string{"ollama", "pull", model}); err != nil {
				return err
			}
		}
		return nil
	},
}
