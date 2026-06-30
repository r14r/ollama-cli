package blobscan

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func CollectBlobMappings(manifestRoot string) map[string][]string {
	blobToModels := make(map[string][]string)

	filepath.Walk(manifestRoot, func(path string, info os.FileInfo, err error) error {
		if err != nil || info.IsDir() {
			return nil
		}

		data, err := os.ReadFile(path)
		if err != nil {
			return nil
		}

		var manifest map[string]interface{}
		if err := json.Unmarshal(data, &manifest); err != nil {
			return nil
		}

		relPath, _ := filepath.Rel(manifestRoot, path)
		modelName := NormalizeModelName(relPath)

		addDigest := func(digest interface{}) {
			if digestStr, ok := digest.(string); ok && strings.HasPrefix(digestStr, "sha256:") {
				hash := strings.TrimPrefix(digestStr, "sha256:")
				blobToModels[hash] = append(blobToModels[hash], modelName)
			}
		}

		if cfg, ok := manifest["config"].(map[string]interface{}); ok {
			if d, ok := cfg["digest"]; ok {
				addDigest(d)
			}
		}

		if layers, ok := manifest["layers"].([]interface{}); ok {
			for _, layer := range layers {
				if layerMap, ok := layer.(map[string]interface{}); ok {
					if d, ok := layerMap["digest"]; ok {
						addDigest(d)
					}
				}
			}
		}

		return nil
	})

	// Deduplicate
	for k := range blobToModels {
		sort.Strings(blobToModels[k])
		seen := make(map[string]bool)
		var unique []string
		for _, m := range blobToModels[k] {
			if !seen[m] {
				unique = append(unique, m)
				seen[m] = true
			}
		}
		blobToModels[k] = unique
	}

	return blobToModels
}

func ListAllBlobs(blobsRoot string) []string {
	blobs := make(map[string]bool)

	entries, err := os.ReadDir(blobsRoot)
	if err != nil {
		return nil
	}

	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()

		if strings.HasPrefix(name, "sha256-") && len(name) > len("sha256-") {
			blobs[name[len("sha256-"):]] = true
			continue
		}

		if h := extractBlobHashRelaxed(name); h != "" {
			blobs[h] = true
		}
	}

	var result []string
	for b := range blobs {
		result = append(result, b)
	}
	sort.Strings(result)
	return result
}

func extractBlobHashRelaxed(name string) string {
	n := strings.ToLower(name)
	if idx := strings.Index(n, "."); idx >= 0 {
		n = n[:idx]
	}

	if strings.HasPrefix(n, "sha256") {
		n = n[len("sha256"):]
	}

	if len(n) < 40 || len(n) > 128 {
		return ""
	}

	for _, c := range n {
		if !((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')) {
			return ""
		}
	}

	return n
}

func NormalizeModelName(modelPath string) string {
	if strings.HasPrefix(modelPath, "library/") {
		modelPath = modelPath[len("library/"):]
	}
	parts := strings.Split(modelPath, "/")
	return parts[0]
}
