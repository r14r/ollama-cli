package cmd

import (
	"github.com/spf13/cobra"
)

var helpCmd = &cobra.Command{
	Use:   "help",
	Short: "Show this help message",
	RunE: func(cmd *cobra.Command, args []string) error {
		rootCmd.Help()
		return nil
	},
}
