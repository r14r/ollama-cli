package cmd

import (
	"fmt"
	"regexp"
	"sort"
	"strings"

	"github.com/spf13/cobra"
	"github.com/r14r/ollama-cli/internal/compose"
	"github.com/r14r/ollama-cli/internal/utils"
)

type ModelRow struct {
	Name             string
	ID               string
	Size             string
	Modified         string
	SizeBytes        int64
	ModifiedSeconds  int64
}

var listCmd = &cobra.Command{
	Use:   "list",
	Short: "List local models in docker container",
	RunE: func(cmd *cobra.Command, args []string) error {
		return listModels(cmd)
	},
}

var lsCmd = &cobra.Command{
	Use:   "ls",
	Short: "List local models (alias of 'list')",
	RunE: func(cmd *cobra.Command, args []string) error {
		return listModels(cmd)
	},
}

func listModels(cmd *cobra.Command, args ...string) error {
	if err := compose.EnsureServiceRunning(); err != nil {
		return err
	}

	out, err := compose.ComposeExecCapture([]string{"ollama", "list"})
	if err != nil {
		return err
	}

	lines := strings.Split(strings.TrimSpace(out), "\n")
	if len(lines) == 0 {
		fmt.Println("No models found.")
		return nil
	}

	header := strings.TrimSpace(lines[0])
	if !strings.HasPrefix(header, "NAME") {
		fmt.Println(out)
		return nil
	}

	var rows []ModelRow
	reMultiSpace := regexp.MustCompile(`\s{2,}`)

	for _, line := range lines[1:] {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := reMultiSpace.Split(line, -1)
		var cleanParts []string
		for _, p := range parts {
			if p = strings.TrimSpace(p); p != "" {
				cleanParts = append(cleanParts, p)
			}
		}

		if len(cleanParts) >= 4 {
			rows = append(rows, ModelRow{
				Name:            cleanParts[0],
				ID:              cleanParts[1],
				Size:            cleanParts[2],
				Modified:        cleanParts[3],
				SizeBytes:       utils.ParseSizeToBytes(cleanParts[2]),
				ModifiedSeconds: utils.ParseRelativeTimeToSeconds(cleanParts[3]),
			})
		} else if len(cleanParts) == 3 {
			rows = append(rows, ModelRow{
				Name:            cleanParts[0],
				ID:              cleanParts[1],
				Size:            cleanParts[2],
				Modified:        "unknown",
				SizeBytes:       utils.ParseSizeToBytes(cleanParts[2]),
				ModifiedSeconds: 9999999999,
			})
		}
	}

	sortBy, _ := cmd.Flags().GetString("sort-by")
	sortAsc, _ := cmd.Flags().GetBool("sort-asc")
	sortDesc, _ := cmd.Flags().GetBool("sort-desc")

	reverse := sortDesc
	if sortAsc {
		reverse = false
	}

	sort.Slice(rows, func(i, j int) bool {
		cmp := 0
		switch sortBy {
		case "size":
			if rows[i].SizeBytes != rows[j].SizeBytes {
				cmp = -1
				if rows[i].SizeBytes > rows[j].SizeBytes {
					cmp = 1
				}
			}
		case "modified":
			if rows[i].ModifiedSeconds != rows[j].ModifiedSeconds {
				cmp = -1
				if rows[i].ModifiedSeconds > rows[j].ModifiedSeconds {
					cmp = 1
				}
			}
		case "id":
			cmp = strings.Compare(strings.ToLower(rows[i].ID), strings.ToLower(rows[j].ID))
		default: // name
			cmp = strings.Compare(strings.ToLower(rows[i].Name), strings.ToLower(rows[j].Name))
		}
		if reverse {
			cmp = -cmp
		}
		return cmp < 0
	})

	if len(rows) == 0 {
		fmt.Println("No models found.")
		return nil
	}

	// Print table
	widths := map[string]int{
		"NAME":     len("NAME"),
		"ID":       len("ID"),
		"SIZE":     len("SIZE"),
		"MODIFIED": len("MODIFIED"),
	}
	for _, r := range rows {
		if len(r.Name) > widths["NAME"] {
			widths["NAME"] = len(r.Name)
		}
		if len(r.ID) > widths["ID"] {
			widths["ID"] = len(r.ID)
		}
		if len(r.Size) > widths["SIZE"] {
			widths["SIZE"] = len(r.Size)
		}
		if len(r.Modified) > widths["MODIFIED"] {
			widths["MODIFIED"] = len(r.Modified)
		}
	}

	header = fmt.Sprintf("%s  %s  %s  %s",
		padRight("NAME", widths["NAME"]),
		padRight("ID", widths["ID"]),
		padRight("SIZE", widths["SIZE"]),
		padRight("MODIFIED", widths["MODIFIED"]))
	fmt.Println(header)

	for _, r := range rows {
		line := fmt.Sprintf("%s  %s  %s  %s",
			padRight(r.Name, widths["NAME"]),
			padRight(r.ID, widths["ID"]),
			padRight(r.Size, widths["SIZE"]),
			padRight(r.Modified, widths["MODIFIED"]))
		fmt.Println(line)
	}

	return nil
}

func padRight(s string, width int) string {
	if len(s) >= width {
		return s
	}
	return s + strings.Repeat(" ", width-len(s))
}

func init() {
	listCmd.Flags().String("sort-by", "name", "Sort models by column (name, size, modified, id)")
	listCmd.Flags().Bool("sort-asc", false, "Sort ascending (default)")
	listCmd.Flags().Bool("sort-desc", false, "Sort descending")

	lsCmd.Flags().String("sort-by", "name", "Sort models by column (name, size, modified, id)")
	lsCmd.Flags().Bool("sort-asc", false, "Sort ascending (default)")
	lsCmd.Flags().Bool("sort-desc", false, "Sort descending")
}
