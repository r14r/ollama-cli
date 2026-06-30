package models

import (
	"strings"

	"github.com/r14r/ollama-cli/internal/compose"
)

func EnsureModelExists(model string) bool {
	out, err := compose.ComposeExecCapture([]string{"ollama", "list"})
	if err != nil {
		return false
	}
	for i, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if i == 0 && strings.HasPrefix(line, "NAME") {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) > 0 && parts[0] == model {
			return true
		}
	}
	return false
}

func EnsureModelPulled(model string) error {
	if EnsureModelExists(model) {
		return nil
	}
	return compose.ComposeExec([]string{"ollama", "pull", model})
}

func GetInstalledModels() []string {
	out, err := compose.ComposeExecCapture([]string{"ollama", "list"})
	if err != nil {
		return nil
	}
	var models []string
	for i, line := range strings.Split(out, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		if i == 0 && strings.HasPrefix(line, "NAME") {
			continue
		}
		parts := strings.Fields(line)
		if len(parts) > 0 {
			models = append(models, parts[0])
		}
	}
	return models
}
