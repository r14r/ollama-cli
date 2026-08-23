package cmd

import (
	"fmt"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
	"github.com/r14r/ollama-cli/internal/config"
)

var buildCmd = &cobra.Command{
	Use:   "build",
	Short: "Pull base image and rebuild the Ollama service",
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := compose.RunCmd([]string{"docker", "pull", "ollama/ollama:latest"}); err != nil {
			return err
		}
		if err := compose.RunCmd(compose.BuildComposeCmd("build")); err != nil {
			return err
		}

		withModels, _ := cmd.Flags().GetString("with-models")
		if withModels == "" {
			return nil
		}

		modelList, err := config.GetModelsFromFile(withModels)
		if err != nil {
			return err
		}

		if err := compose.EnsureServiceRunning(); err != nil {
			return err
		}

		for _, model := range modelList {
			fmt.Printf("==> ollama pull %s\n", model)
			if err := compose.ComposeExec([]string{"ollama", "pull", model}); err != nil {
				return err
			}
		}
		return nil
	},
}

func init() {
	buildCmd.Flags().String("with-models", "", "Path to a models file (top-level 'models:' list) to pull after build")
}
