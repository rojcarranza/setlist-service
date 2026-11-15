// Package song is the smallest unit of a setlist: a song in a key.
package song

import (
	"errors"
	"strings"
)

// Song is one song a worship team can play.
type Song struct {
	ID     string `json:"id"`
	Title  string `json:"title"`
	Artist string `json:"artist"`
	Key    string `json:"key"`
	BPM    int    `json:"bpm"`
}

// Validate reports why a song cannot be added to a setlist.
func (s Song) Validate() error {
	switch {
	case strings.TrimSpace(s.Title) == "":
		return errors.New("song needs a title")
	case s.Key == "":
		return errors.New("song needs a key")
	case s.BPM < 40 || s.BPM > 220:
		return errors.New("bpm must be between 40 and 220")
	}
	return nil
}
