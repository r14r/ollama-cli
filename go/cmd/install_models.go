package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
	"github.com/r14r/ollama-cli/internal/config"
)

var installModelsCmd = &cobra.Command{
	Use:   "install-models",
	Short: "Pull a specific group of models from setup.yml",
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := compose.EnsureServiceRunning(); err != nil {
			return err
		}

		group, _ := cmd.Flags().GetString("group")
		groupModels, err := config.GetGroupModels(group)
		if err != nil {
			return err
		}

		fmt.Printf("Pulling group '%s' models into Ollama volume for service '%s'...\n", group, compose.SERVICE)
		fmt.Println("Models:")
		for _, m := range groupModels {
			fmt.Printf("  %s\n", m)
		}
		fmt.Println()

		for _, model := range groupModels {
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

func init() {
	installModelsCmd.Flags().StringP("group", "", "", "Model group name (e.g. reasoning, fast)")
	installModelsCmd.MarkFlagRequired("group")
}
