package main

import (
	"os"

	"github.com/r14r/ollama-cli/cmd"
)

func main() {
	// Translate --up, --down, etc. to positional subcommands
	args := os.Args[1:]
	for i, arg := range args {
		if arg == "--up" {
			args[i] = "up"
		} else if arg == "--down" {
			args[i] = "down"
		} else if arg == "--build" {
			args[i] = "build"
		} else if arg == "--status" {
			args[i] = "status"
		} else if arg == "--profiles" {
			args[i] = "profiles"
		} else if arg == "--install-defaults" {
			args[i] = "install-defaults"
		} else if arg == "--launch" {
			args[i] = "launch"
		} else if arg == "--list-remote" {
			args[i] = "list-remote"
		} else if arg == "--shell" {
			args[i] = "shell"
		} else if arg == "--update-models" {
			args[i] = "update-models"
		} else if arg == "--blobs" {
			args[i] = "blobs"
		} else if arg == "--models" {
			args[i] = "models"
		} else if arg == "--setup" {
			args[i] = "setup"
		} else if arg == "--install-models" {
			args[i] = "install-models"
		} else if arg == "--version" {
			args[i] = "version"
		}
	}
	os.Args = append([]string{os.Args[0]}, args...)

	if err := cmd.Execute(); err != nil {
		os.Exit(1)
	}
}
