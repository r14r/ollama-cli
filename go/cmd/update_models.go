package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
	"github.com/r14r/ollama-cli/internal/config"
	"github.com/r14r/ollama-cli/internal/models"
)

var updateModelsCmd = &cobra.Command{
	Use:   "update-models",
	Short: "Pull the latest version for all installed models",
	RunE: func(cmd *cobra.Command, args []string) error {
		withModels, _ := cmd.Flags().GetString("with-models")

		modelList := models.GetInstalledModels()
		if withModels != "" {
			list, err := config.GetModelsFromFile(withModels)
			if err != nil {
				return err
			}
			modelList = list
		}

		for _, model := range modelList {
			fmt.Printf("Update '%s'\n", model)
			if err := compose.ComposeExec([]string{"ollama", "pull", model}); err != nil {
				return err
			}
		}
		return nil
	},
}

func init() {
	updateModelsCmd.Flags().String("with-models", "", "Path to a models file (top-level 'models:' list) to pull instead of currently installed models")
}
