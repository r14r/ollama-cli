package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
)

var profilesCmd = &cobra.Command{
	Use:   "profiles",
	Short: "List launch profiles",
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
		fmt.Println("Available launch profiles:")
		for _, name := range []string{"claude", "opencode", "chat", "fast", "reason", "embed", "hermes"} {
			model := profiles[name]
			if model == "" {
				model = defaults[name]
			}
			fmt.Printf("  %-10s -> %s\n", name, model)
		}
		return nil
	},
}
