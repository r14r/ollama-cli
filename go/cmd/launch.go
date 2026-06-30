package cmd

import (
	"fmt"
	"os"
	"strings"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
	"github.com/r14r/ollama-cli/internal/models"
)

var launchCmd = &cobra.Command{
	Use:   "launch",
	Short: "Launch a predefined profile",
	Args:  cobra.MinimumNArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		profiles := map[string]string{
			"claude":     os.Getenv("OLLAMA_LAUNCH_CLAUDE_MODEL"),
			"opencode":   os.Getenv("OLLAMA_LAUNCH_OPENCODE_MODEL"),
			"chat":       os.Getenv("OLLAMA_LAUNCH_CHAT_MODEL"),
			"fast":       os.Getenv("OLLAMA_LAUNCH_FAST_MODEL"),
			"reason":     os.Getenv("OLLAMA_LAUNCH_REASON_MODEL"),
			"embed":      os.Getenv("OLLAMA_LAUNCH_EMBED_MODEL"),
			"hermes":     os.Getenv("OLLAMA_LAUNCH_HERMES_MODEL"),
		}
		defaults := map[string]string{
			"claude":     "qwen2.5:7b-instruct",
			"opencode":   "qwen2.5:7b-instruct",
			"chat":       "mistral:7b-instruct",
			"fast":       "llama3.2:1b",
			"reason":     "deepseek-r1",
			"embed":      "nomic-embed-text",
			"hermes":     "phi4-mini",
		}

		profile := args[0]
		model := profiles[profile]
		if model == "" {
			model = defaults[profile]
		}
		if model == "" {
			fmt.Fprintf(os.Stderr, "ERROR: unknown launch profile '%s'\n", profile)
			fmt.Fprintf(os.Stderr, "Run 'profiles' to see available profiles.\n")
			os.Exit(2)
		}

		if err := compose.EnsureServiceRunning(); err != nil {
			return err
		}
		if err := models.EnsureModelPulled(model); err != nil {
			return err
		}

		fmt.Printf("Launching profile '%s' with model '%s'...\n", profile, model)

		launchArgs := []string{"ollama", "run", model}
		if len(args) > 1 {
			launchArgs = append(launchArgs, strings.Join(args[1:], " "))
		}
		return compose.ComposeExec(launchArgs)
	},
}
