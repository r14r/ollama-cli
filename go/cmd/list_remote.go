package cmd

import (
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"time"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/remote"
	"github.com/r14r/ollama-cli/internal/utils"
)

var listRemoteCmd = &cobra.Command{
	Use:   "list-remote",
	Short: "List models from the Ollama library website",
	RunE: func(cmd *cobra.Command, args []string) error {
		limit, _ := cmd.Flags().GetInt("limit")
		withDesc, _ := cmd.Flags().GetBool("with-description")
		filterCaps, _ := cmd.Flags().GetStringSlice("filter")
		sortBy, _ := cmd.Flags().GetString("sort-by")
		force, _ := cmd.Flags().GetBool("force")
		showCache, _ := cmd.Flags().GetBool("show-cache")
		modelName, _ := cmd.Flags().GetString("model")

		cacheDir, _ := remote.GetCacheDir()

		if showCache {
			if modelName != "" {
				jsonFile := filepath.Join(cacheDir, modelName+".json")
				if data, err := os.ReadFile(jsonFile); err == nil {
					fmt.Println(string(data))
				} else {
					fmt.Printf("No cached JSON info found for model '%s'.\n", modelName)
					fmt.Printf("Expected path: %s\n", jsonFile)
				}
				return nil
			}

			fmt.Printf("Cache folder: %s\n", cacheDir)
			entries, err := os.ReadDir(cacheDir)
			if err != nil {
				fmt.Println("Cache is empty (folder does not exist).")
				return nil
			}

			var files []os.DirEntry
			for _, e := range entries {
				if !e.IsDir() && strings.HasSuffix(e.Name(), ".html") {
					files = append(files, e)
				}
			}

			if len(files) == 0 {
				fmt.Println("Cache is empty.")
				return nil
			}

			fmt.Printf("Cached files (%d):\n", len(files))
			totalSize := int64(0)
			for _, f := range files {
				info, _ := f.Info()
				size := info.Size()
				totalSize += size
				mtime := info.ModTime()
				ageSec := time.Since(mtime).Seconds()

				var ageStr string
				if ageSec < 60 {
					ageStr = fmt.Sprintf("%ds ago", int(ageSec))
				} else if ageSec < 3600 {
					ageStr = fmt.Sprintf("%dm ago", int(ageSec/60))
				} else if ageSec < 86400 {
					ageStr = fmt.Sprintf("%dh ago", int(ageSec/3600))
				} else {
					ageStr = fmt.Sprintf("%dd ago", int(ageSec/86400))
				}

				var sizeStr string
				sizeKB := float64(size) / 1024
				if sizeKB < 1024 {
					sizeStr = fmt.Sprintf("%.1f KB", sizeKB)
				} else {
					sizeStr = fmt.Sprintf("%.1f MB", sizeKB/1024)
				}
				fmt.Printf("  %-25s (%s / %s)\n", f.Name(), sizeStr, ageStr)
			}

			totalSizeKB := float64(totalSize) / 1024
			var totalSizeStr string
			if totalSizeKB < 1024 {
				totalSizeStr = fmt.Sprintf("%.1f KB", totalSizeKB)
			} else {
				totalSizeStr = fmt.Sprintf("%.1f MB", totalSizeKB/1024)
			}
			fmt.Printf("Total size: %s\n", totalSizeStr)
			return nil
		}

		fmt.Println("Downloading main models list from https://ollama.com/library...")
		client := &http.Client{Timeout: 30 * time.Second}
		resp, err := client.Get("https://ollama.com/library")
		if err != nil {
			return err
		}
		defer resp.Body.Close()

		if resp.StatusCode != 200 {
			return fmt.Errorf("HTTP %d", resp.StatusCode)
		}

		data, err := io.ReadAll(resp.Body)
		if err != nil {
			return err
		}

		tagsRows, err := remote.ExtractModels(string(data), limit, withDesc, filterCaps, sortBy, force)
		if err != nil {
			return err
		}

		if len(tagsRows) == 0 {
			fmt.Println("No remote models or matching tags found.")
			return nil
		}

		// Filter by capabilities
		var normalizedCaps map[string]bool
		if len(filterCaps) > 0 {
			normalizedCaps = make(map[string]bool)
			for _, cap := range filterCaps {
				normalizedCaps[strings.ToLower(strings.TrimSpace(cap))] = true
			}

			var filtered []remote.TagRow
			for _, r := range tagsRows {
				found := false
				for _, cap := range r.Capabilities {
					if normalizedCaps[strings.ToLower(cap)] {
						found = true
						break
					}
				}
				if found {
					filtered = append(filtered, r)
				}
			}
			tagsRows = filtered
		}

		if len(tagsRows) == 0 {
			fmt.Println("No remote models matched the capability filters.")
			return nil
		}

		// Sort
		sort.Slice(tagsRows, func(i, j int) bool {
			switch sortBy {
			case "capability":
				if strings.Join(tagsRows[i].Capabilities, ",") != strings.Join(tagsRows[j].Capabilities, ",") {
					return strings.Join(tagsRows[i].Capabilities, ",") < strings.Join(tagsRows[j].Capabilities, ",")
				}
				return tagsRows[i].ModelName < tagsRows[j].ModelName
			case "size":
				return tagsRows[i].Sizes < tagsRows[j].Sizes
			case "date":
				return utils.ParseRelativeTimeToSeconds(tagsRows[i].Updated) < utils.ParseRelativeTimeToSeconds(tagsRows[j].Updated)
			case "name":
				return tagsRows[i].ModelName < tagsRows[j].ModelName
			default:
				return tagsRows[i].Order < tagsRows[j].Order
			}
		})

		// Limit
		if limit > 0 && len(tagsRows) > limit {
			tagsRows = tagsRows[:limit]
		}

		columns := []string{"model_name", "capabilities", "sizes", "usage", "updated"}
		if withDesc {
			columns = append(columns, "description")
		}

		var printRows [][]string
		for _, row := range tagsRows {
			size := row.Sizes
			printRow := []string{
				row.ModelName,
				strings.Join(row.Capabilities, ", "),
				size,
				row.Usage,
				row.Updated,
			}
			if withDesc {
				printRow = append(printRow, row.Description)
			}
			printRows = append(printRows, printRow)
		}

		colWidths := make(map[string]int)
		for _, col := range columns {
			colWidths[col] = len(col)
		}
		for _, row := range printRows {
			for i, val := range row {
				if colWidths[columns[i]] < len(val) {
					colWidths[columns[i]] = len(val)
				}
			}
		}

		if withDesc {
			header := ""
			for i := 0; i < len(columns)-1; i++ {
				if i > 0 {
					header += "  "
				}
				header += padRight(columns[i], colWidths[columns[i]])
			}
			fmt.Println(header)
			fmt.Println()

			for _, row := range printRows {
				for i := 0; i < len(row)-1; i++ {
					if i > 0 {
						fmt.Print("  ")
					}
					fmt.Print(padRight(row[i], colWidths[columns[i]]))
				}
				fmt.Println()
				fmt.Println(row[len(row)-1])
				fmt.Println()
			}
		} else {
			header := ""
			for i, col := range columns {
				if i > 0 {
					header += "  "
				}
				header += padRight(col, colWidths[col])
			}
			fmt.Println(header)

			for _, row := range printRows {
				line := ""
				for i, val := range row {
					if i > 0 {
						line += "  "
					}
					line += padRight(val, colWidths[columns[i]])
				}
				fmt.Println(line)
			}
		}

		return nil
	},
}

func init() {
	listRemoteCmd.Flags().IntP("limit", "", 25, "Maximum number of rows to show; use 0 for all")
	listRemoteCmd.Flags().Bool("with-description", false, "Print the description below each row")
	listRemoteCmd.Flags().StringSliceP("filter", "", nil, "Filter by capability; may be specified multiple times")
	listRemoteCmd.Flags().String("sort-by", "name", "Sort output by (order, capability, size, date, name)")
	listRemoteCmd.Flags().Bool("force", false, "Bypass/refresh the cache of remote models metadata")
	listRemoteCmd.Flags().Bool("show-cache", false, "Show the cache folder and list cached files")
	listRemoteCmd.Flags().String("model", "", "Specify model name to show cached JSON content (used with --show-cache)")
}
