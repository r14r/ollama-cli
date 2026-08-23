package cmd

import (
	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
)

var rebuildCmd = &cobra.Command{
	Use:   "rebuild",
	Short: "Pull latest base images, clean-build all services, and start the stack",
	RunE: func(cmd *cobra.Command, args []string) error {
		if err := compose.RunCmd(compose.BuildComposeCmd("pull")); err != nil {
			return err
		}
		if err := compose.RunCmd(compose.BuildComposeCmd("build", "--no-cache", "--pull")); err != nil {
			return err
		}
		return compose.RunCmd(compose.BuildComposeCmd("up", "-d"))
	},
}
