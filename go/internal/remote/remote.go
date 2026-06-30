package remote

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"
)

func GetCacheDir() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	cacheDir := filepath.Join(home, ".ollama-cli", "cache")
	if err := os.MkdirAll(cacheDir, 0755); err != nil {
		return "", err
	}
	return cacheDir, nil
}

func FetchAndCacheHTML(url string, cacheFile string, force bool) (string, error) {
	// Check cache first if not forced
	if !force {
		if data, err := os.ReadFile(cacheFile); err == nil {
			if stat, err := os.Stat(cacheFile); err == nil {
				// 24 hour cache validity
				if time.Since(stat.ModTime()) < 24*time.Hour {
					return string(data), nil
				}
			}
		}
	}

	// Fetch from URL
	resp, err := http.Get(url)
	if err != nil {
		// Try fallback to expired cache
		if data, err := os.ReadFile(cacheFile); err == nil {
			return string(data), nil
		}
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != 200 {
		// Try fallback to expired cache
		if data, err := os.ReadFile(cacheFile); err == nil {
			return string(data), nil
		}
		return "", fmt.Errorf("HTTP %d", resp.StatusCode)
	}

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", err
	}

	// Save to cache
	os.WriteFile(cacheFile, body, 0644)

	return string(body), nil
}

type TagRow struct {
	ModelName    string
	Capabilities []string
	Sizes        string
	Usage        string
	Context      string
	Input        string
	Updated      string
	Description  string
	Order        int
}

func ExtractModels(html string, limit int, withDesc bool, filterCaps []string, sortBy string, force bool) ([]TagRow, error) {
	doc, err := goquery.NewDocumentFromReader(strings.NewReader(html))
	if err != nil {
		return nil, err
	}

	cacheDir, _ := GetCacheDir()

	var baseModels []map[string]interface{}

	doc.Find("li[x-test-model]").Each(func(i int, s *goquery.Selection) {
		nameDiv := s.Find("div[title]")
		if nameDiv.Length() == 0 {
			return
		}
		modelName, _ := nameDiv.Attr("title")

		descP := s.Find("p.max-w-lg")
		description := descP.Text()

		var capabilities []string
		container := s.Find("div.flex.flex-wrap.space-x-2")
		container.Find("span.inline-flex").Each(func(j int, sp *goquery.Selection) {
			if _, ok := sp.Attr("x-test-size"); ok {
				return
			}
			text := strings.ToLower(strings.TrimSpace(sp.Text()))
			if text != "" {
				capabilities = append(capabilities, text)
			}
		})

		baseModels = append(baseModels, map[string]interface{}{
			"model_name":    modelName,
			"description":   description,
			"capabilities": capabilities,
		})
	})

	var tagsRows []TagRow
	targetTags := map[string]bool{
		"latest": true, "cloud": true, "e2b": true, "e4b": true, "12b": true,
		"26b": true, "31b": true, "vision": true, "tools": true, "thinking": true, "audio": true,
	}

	for order, bm := range baseModels {
		modelName := bm["model_name"].(string)
		url := fmt.Sprintf("https://ollama.com/library/%s/tags", modelName)
		cacheFile := filepath.Join(cacheDir, modelName+".html")

		html, err := FetchAndCacheHTML(url, cacheFile, force)
		if err != nil {
			continue
		}

		doc, err := goquery.NewDocumentFromReader(strings.NewReader(html))
		if err != nil {
			continue
		}

		seenHrefs := make(map[string]bool)
		doc.Find("a").Each(func(i int, s *goquery.Selection) {
			href, _ := s.Attr("href")
			if !strings.HasPrefix(href, fmt.Sprintf("/library/%s:", modelName)) {
				return
			}
			if seenHrefs[href] {
				return
			}
			seenHrefs[href] = true

			fullTagName := strings.TrimPrefix(href, "/library/")
			parts := strings.Split(fullTagName, ":")
			tagSuffix := ""
			if len(parts) > 1 {
				tagSuffix = parts[1]
			}

			if !targetTags[strings.ToLower(tagSuffix)] {
				return
			}

			text := s.Text()
			textParts := strings.Split(text, "•")

			var sizeOrUsage, inputType, context, updated string
			for _, p := range textParts {
				p = strings.TrimSpace(p)
				pLower := strings.ToLower(p)
				if strings.Contains(pLower, "gb") || strings.Contains(pLower, "mb") || strings.Contains(pLower, "kb") || strings.Contains(pLower, "usage") {
					sizeOrUsage = p
				} else if strings.Contains(pLower, "input") {
					inputType = p
				} else if strings.Contains(pLower, "context") {
					context = p
				} else if strings.Contains(pLower, "ago") || strings.Contains(pLower, "hour") || strings.Contains(pLower, "day") || strings.Contains(pLower, "month") || strings.Contains(pLower, "year") {
					updated = strings.Split(p, "\n")[0]
				}
			}

			var caps []string
			if strings.Contains(strings.ToLower(inputType), "image") || strings.Contains(strings.ToLower(text), "vision") {
				caps = append(caps, "vision")
			}
			for _, cap := range []string{"tools", "thinking", "audio"} {
				if strings.Contains(strings.ToLower(text), cap) {
					caps = append(caps, cap)
				}
			}
			if strings.ToLower(tagSuffix) == "cloud" {
				caps = append(caps, "cloud")
			}

			tagsRows = append(tagsRows, TagRow{
				ModelName:    fullTagName,
				Capabilities: caps,
				Sizes:        tagSuffix,
				Usage:        sizeOrUsage,
				Context:      context,
				Input:        inputType,
				Updated:      updated,
				Description:  bm["description"].(string),
				Order:        order,
			})

			// Save model JSON
			jsonFile := filepath.Join(cacheDir, modelName+".json")
			jsonData := map[string]interface{}{
				"model_name":     modelName,
				"description":    bm["description"],
				"base_capabilities": bm["capabilities"],
				"tags": []TagRow{{ModelName: fullTagName, Capabilities: caps, Sizes: tagSuffix}},
			}
			if b, err := json.MarshalIndent(jsonData, "", "  "); err == nil {
				os.WriteFile(jsonFile, b, 0644)
			}
		})
	}

	return tagsRows, nil
}
