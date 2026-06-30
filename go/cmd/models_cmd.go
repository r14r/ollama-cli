package cmd

import (
	"encoding/csv"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/blobscan"
	"github.com/r14r/ollama-cli/internal/utils"
)

var modelsCmd = &cobra.Command{
	Use:   "models",
	Short: "List models with blob counts and total disk usage",
	RunE: func(cmd *cobra.Command, args []string) error {
		modelsRoot, _ := cmd.Flags().GetString("models-root")
		root := os.ExpandEnv(filepath.Join(os.Getenv("HOME"), modelsRoot))
		if strings.HasPrefix(modelsRoot, "/") {
			root = modelsRoot
		}

		manifestRoot := filepath.Join(root, "manifests", "registry.ollama.ai")
		blobsRoot := filepath.Join(root, "blobs")

		blobToModels := blobscan.CollectBlobMappings(manifestRoot)
		blobs := blobscan.ListAllBlobs(blobsRoot)

		// Precompute blob sizes
		blobSizes := make(map[string]int64)
		for _, hash := range blobs {
			blobFile := filepath.Join(blobsRoot, "sha256-"+hash)
			if stat, err := os.Stat(blobFile); err == nil {
				blobSizes[hash] = stat.Size()
			}
		}

		// Aggregate per model
		type ModelInfo struct {
			Name       string
			BlobCount  int
			TotalBytes int64
		}
		modelInfo := make(map[string]*ModelInfo)

		for hash, models := range blobToModels {
			size := blobSizes[hash]
			for _, m := range models {
				if _, ok := modelInfo[m]; !ok {
					modelInfo[m] = &ModelInfo{Name: m}
				}
				modelInfo[m].BlobCount++
				modelInfo[m].TotalBytes += size
			}
		}

		var rows []map[string]string
		for _, info := range modelInfo {
			format, _ := cmd.Flags().GetString("format")
			rows = append(rows, map[string]string{
				"model":       info.Name,
				"blob_count":  fmt.Sprintf("%d", info.BlobCount),
				"total_bytes": fmt.Sprintf("%d", info.TotalBytes),
				"total_size":  utils.FormatSize(info.TotalBytes, format),
			})
		}

		// Sorting
		sortBySize, _ := cmd.Flags().GetBool("sort-by-size")
		sortDesc, _ := cmd.Flags().GetBool("sort-desc")

		sort.Slice(rows, func(i, j int) bool {
			var less bool
			if sortBySize {
				var iBytes, jBytes int64
				fmt.Sscanf(rows[i]["total_bytes"], "%d", &iBytes)
				fmt.Sscanf(rows[j]["total_bytes"], "%d", &jBytes)
				less = iBytes < jBytes
			} else {
				less = rows[i]["model"] < rows[j]["model"]
			}
			if sortDesc {
				less = !less
			}
			return less
		})

		// Output
		asCSV, _ := cmd.Flags().GetBool("as-csv")
		outPath, _ := cmd.Flags().GetString("output")
		columns := []string{"model", "blob_count", "total_size", "total_bytes"}

		if asCSV {
			var file *os.File
			var err error
			if outPath == "-" || outPath == "" {
				file = os.Stdout
			} else {
				file, err = os.Create(outPath)
				if err != nil {
					return err
				}
				defer file.Close()
			}

			writer := csv.NewWriter(file)
			writer.Write(columns)
			for _, r := range rows {
				var record []string
				for _, col := range columns {
					record = append(record, r[col])
				}
				writer.Write(record)
			}
			writer.Flush()
		} else {
			noColor, _ := cmd.Flags().GetBool("no-color")
			enableColor := !noColor && utils.SupportsColor()

			widths := make(map[string]int)
			for _, col := range columns {
				widths[col] = len(col)
			}
			for _, r := range rows {
				for _, col := range columns {
					if len(r[col]) > widths[col] {
						widths[col] = len(r[col])
					}
				}
			}

			header := ""
			for i, col := range columns {
				if i > 0 {
					header += "  "
				}
				header += padRight(col, widths[col])
			}
			fmt.Println(utils.Colorize(header, "1;37", enableColor))

			for _, r := range rows {
				line := ""
				for i, col := range columns {
					if i > 0 {
						line += "  "
					}
					line += padRight(r[col], widths[col])
				}
				fmt.Println(line)
			}
		}

		return nil
	},
}

func init() {
	modelsCmd.Flags().String("models-root", "~/.ollama/models", "")
	modelsCmd.Flags().String("format", "mb", "Format for human-readable size (mb, gb)")
	modelsCmd.Flags().Bool("as-csv", false, "Output as CSV")
	modelsCmd.Flags().StringP("output", "o", "-", "CSV output path (default: stdout)")
	modelsCmd.Flags().Bool("sort-by-size", false, "Sort by total model size")
	modelsCmd.Flags().Bool("sort-desc", false, "Sort descending (default: asc)")
	modelsCmd.Flags().Bool("no-color", false, "Disable colored output")
}
