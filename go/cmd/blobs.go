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

var blobsCmd = &cobra.Command{
	Use:   "blobs",
	Short: "Inspect blobs, manifests and orphans in the Ollama models directory",
	RunE: func(cmd *cobra.Command, args []string) error {
		modelsRoot, _ := cmd.Flags().GetString("models-root")
		modelsRoot = filepath.Join(os.ExpandEnv(modelsRoot))

		root := os.ExpandEnv(filepath.Join(os.Getenv("HOME"), modelsRoot))
		if !strings.HasPrefix(modelsRoot, "/") && !strings.HasPrefix(modelsRoot, "~") {
			root = filepath.Join(os.ExpandEnv("~"), modelsRoot)
		}

		manifestRoot := filepath.Join(root, "manifests", "registry.ollama.ai")
		blobsRoot := filepath.Join(root, "blobs")

		debug, _ := cmd.Flags().GetBool("debug")
		if debug {
			fmt.Printf("DEBUG: models_root   = %s\n", root)
			fmt.Printf("DEBUG: manifest_root = %s\n", manifestRoot)
			fmt.Printf("DEBUG: blobs_root    = %s\n", blobsRoot)
		}

		blobToModels := blobscan.CollectBlobMappings(manifestRoot)
		blobs := blobscan.ListAllBlobs(blobsRoot)

		if debug {
			fmt.Printf("DEBUG: total blobs found in blobs/ = %d\n", len(blobs))
		}

		type Row struct {
			Blob     string
			Models   string
			SizeB    int64
			Size     string
			IsOrphan string
		}

		var rows []Row
		var orphanFiles []string

		totalBlobs := len(blobs)
		showProgress, _ := cmd.Flags().GetBool("progress")
		if showProgress && totalBlobs > 0 {
			fmt.Printf("Processing %d blobs...\n", totalBlobs)
		}

		for idx, blobHash := range blobs {
			if showProgress && totalBlobs > 0 {
				fmt.Printf("\rBlobs: [%-30s] %d/%d", strings.Repeat("#", idx*30/totalBlobs), idx+1, totalBlobs)
			}

			blobFile := filepath.Join(blobsRoot, "sha256-"+blobHash)
			models := blobToModels[blobHash]
			sort.Strings(models)

			stat, _ := os.Stat(blobFile)
			var bsize int64
			if stat != nil {
				bsize = stat.Size()
			}

			format, _ := cmd.Flags().GetString("format")
			sizeStr := utils.FormatSize(bsize, format)

			isOrphan := len(models) == 0
			if isOrphan {
				orphanFiles = append(orphanFiles, blobFile)
			}

			rows = append(rows, Row{
				Blob:     "sha256-" + blobHash,
				Models:   strings.Join(models, "|"),
				SizeB:    bsize,
				Size:     sizeStr,
				IsOrphan: map[bool]string{true: "yes", false: "no"}[isOrphan],
			})
		}

		if showProgress && totalBlobs > 0 {
			fmt.Println()
		}

		onlyOrphans, _ := cmd.Flags().GetBool("only-orphans")
		if onlyOrphans {
			var filtered []Row
			for _, r := range rows {
				if r.IsOrphan == "yes" {
					filtered = append(filtered, r)
				}
			}
			rows = filtered
		}

		// Sorting
		sortByBlob, _ := cmd.Flags().GetBool("sort-by-blob")
		sortByModel, _ := cmd.Flags().GetBool("sort-by-model")
		sortBySize, _ := cmd.Flags().GetBool("sort-by-size")
		sortDesc, _ := cmd.Flags().GetBool("sort-desc")

		reverse := sortDesc

		sort.Slice(rows, func(i, j int) bool {
			var less bool
			if sortByBlob {
				less = rows[i].Blob < rows[j].Blob
			} else if sortByModel {
				iEmpty := rows[i].Models == ""
				jEmpty := rows[j].Models == ""
				if iEmpty != jEmpty {
					less = iEmpty
				} else {
					less = rows[i].Models < rows[j].Models
				}
			} else if sortBySize {
				less = rows[i].SizeB < rows[j].SizeB
			}
			if reverse {
				less = !less
			}
			return less
		})

		// Output
		columnsStr, _ := cmd.Flags().GetString("columns")
		columns := []string{}
		for _, c := range strings.Split(columnsStr, ",") {
			if c = strings.TrimSpace(c); c != "" {
				columns = append(columns, c)
			}
		}

		if len(columns) == 0 {
			fmt.Fprintf(os.Stderr, "Error: no columns specified\n")
			os.Exit(2)
		}

		asCSV, _ := cmd.Flags().GetBool("as-csv")
		outPath, _ := cmd.Flags().GetString("output")

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
					switch col {
					case "blob":
						record = append(record, r.Blob)
					case "models":
						record = append(record, r.Models)
					case "size_bytes":
						record = append(record, fmt.Sprintf("%d", r.SizeB))
					case "size":
						record = append(record, r.Size)
					case "is_orphan":
						record = append(record, r.IsOrphan)
					}
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
					var val string
					switch col {
					case "blob":
						val = r.Blob
					case "models":
						val = r.Models
					case "size":
						val = r.Size
					case "is_orphan":
						val = r.IsOrphan
					}
					if len(val) > widths[col] {
						widths[col] = len(val)
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
					var val string
					switch col {
					case "blob":
						val = r.Blob
					case "models":
						val = r.Models
					case "size":
						val = r.Size
					case "is_orphan":
						val = r.IsOrphan
					}
					val = padRight(val, widths[col])
					if r.IsOrphan == "yes" {
						val = utils.Colorize(val, "31", enableColor)
					}
					line += val
				}
				fmt.Println(line)
			}
		}

		// Delete orphans
		deleteOrphans, _ := cmd.Flags().GetBool("delete-orphans")
		if deleteOrphans {
			if len(orphanFiles) == 0 {
				fmt.Println("\nNo orphan blobs found.")
				return nil
			}

			fmt.Println("\nOrphan blobs to delete:")
			for _, f := range orphanFiles {
				fmt.Printf("  blobs/%s\n", filepath.Base(f))
			}

			force, _ := cmd.Flags().GetBool("force")
			if !force {
				fmt.Print("Delete? (yes/no) ")
				var confirm string
				fmt.Scanln(&confirm)
				if strings.ToLower(confirm) != "yes" {
					fmt.Println("Aborted.")
					return nil
				}
			}

			for _, f := range orphanFiles {
				if err := os.Remove(f); err == nil {
					fmt.Printf("Deleted: blobs/%s\n", filepath.Base(f))
				} else {
					fmt.Printf("Failed: %s %v\n", f, err)
				}
			}
			fmt.Println("Done.")
		}

		return nil
	},
}

func init() {
	blobsCmd.Flags().String("models-root", "~/.ollama/models", "")
	blobsCmd.Flags().Bool("as-csv", false, "Output as CSV")
	blobsCmd.Flags().StringP("output", "o", "-", "CSV output path (default: stdout)")
	blobsCmd.Flags().Bool("delete-orphans", false, "Delete orphan blobs")
	blobsCmd.Flags().Bool("force", false, "Do not ask before deleting")
	blobsCmd.Flags().Bool("only-orphans", false, "Show only orphans")
	blobsCmd.Flags().Bool("sort-by-blob", false, "Sort by blob name")
	blobsCmd.Flags().Bool("sort-by-model", false, "Sort by first model name")
	blobsCmd.Flags().Bool("sort-by-size", false, "Sort by size in bytes")
	blobsCmd.Flags().Bool("sort-asc", false, "Sort ascending (default)")
	blobsCmd.Flags().Bool("sort-desc", false, "Sort descending")
	blobsCmd.Flags().String("format", "mb", "Format for human-readable size (mb, gb)")
	blobsCmd.Flags().Bool("no-color", false, "Disable colored output")
	blobsCmd.Flags().String("columns", "blob,models,size,is_orphan", "Comma-separated list of columns")
	blobsCmd.Flags().Bool("progress", false, "Show a simple progress bar while processing blobs")
	blobsCmd.Flags().Bool("debug", false, "Print debug information (paths, blob count, etc.)")
	blobsCmd.Flags().String("debug-blob", "", "Hash (without 'sha256-') to debug presence")
}
