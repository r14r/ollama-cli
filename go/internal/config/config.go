package config

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"gopkg.in/yaml.v3"
)

type Config struct {
	Ollama struct {
		DefaultModels []string `yaml:"default_models"`
	} `yaml:"ollama"`
}

func GetConfigPath() string {
	home, _ := os.UserHomeDir()
	return filepath.Join(home, ".ollama-cli", "setup.yml")
}

func GetDefaultModels() []string {
	envModels := os.Getenv("OLLAMA_DEFAULT_MODELS")
	if envModels != "" {
		return strings.Fields(envModels)
	}

	configPath := GetConfigPath()
	data, err := os.ReadFile(configPath)
	if err == nil {
		var cfg Config
		if yaml.Unmarshal(data, &cfg) == nil && len(cfg.Ollama.DefaultModels) > 0 {
			return cfg.Ollama.DefaultModels
		}
	}

	return []string{
		"llama3.2:1b",
		"gemma4:latest",
		"gemma4:e2b",
		"gemma3:1b",
		"gemma3:4b",
		"phi4-mini",
		"phi4-reasoning",
		"phi4-mini-reasoning",
		"phi3:mini",
		"deepseek-r1",
		"qwen3.6:latest",
		"mistral:latest",
		"mistral-nemo:latest",
		"nomic-embed-text-v2-moe",
	}
}

func GetGroupModels(group string) ([]string, error) {
	configPath := GetConfigPath()
	data, err := os.ReadFile(configPath)
	if err != nil {
		return nil, fmt.Errorf("setup file does not exist at %s", configPath)
	}

	var raw map[string]interface{}
	if err := yaml.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("failed to parse setup.yml: %v", err)
	}

	groupKey := group + "_models"
	var models []string

	if ollama, ok := raw["ollama"].(map[string]interface{}); ok {
		if m, ok := ollama[groupKey]; ok {
			models = toStringSlice(m)
		}
	}
	if len(models) == 0 {
		if m, ok := raw[groupKey]; ok {
			models = toStringSlice(m)
		}
	}

	if len(models) == 0 {
		return nil, fmt.Errorf("group '%s' not found in setup.yml", groupKey)
	}
	return models, nil
}

// GetModelsFromFile reads a top-level "models:" list from a YAML file
// (used by `build --with-models` / `update-models --with-models`).
func GetModelsFromFile(path string) ([]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("failed to read models file %s: %v", path, err)
	}

	var raw map[string]interface{}
	if err := yaml.Unmarshal(data, &raw); err != nil {
		return nil, fmt.Errorf("failed to parse models file %s: %v", path, err)
	}

	models := toStringSlice(raw["models"])
	if len(models) == 0 {
		return nil, fmt.Errorf("no models found in %s (expected top-level 'models:' list)", path)
	}
	return models, nil
}

func toStringSlice(v interface{}) []string {
	switch val := v.(type) {
	case []interface{}:
		var result []string
		for _, item := range val {
			result = append(result, fmt.Sprint(item))
		}
		return result
	case string:
		if strings.Contains(val, ",") {
			var result []string
			for _, s := range strings.Split(val, ",") {
				if t := strings.TrimSpace(s); t != "" {
					result = append(result, t)
				}
			}
			return result
		}
		return strings.Fields(val)
	}
	return nil
}
