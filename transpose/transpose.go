// Package transpose moves a musical key up or down by semitones.
package transpose

import (
	"fmt"
	"strings"
)

var sharps = []string{"C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"}

var flatToSharp = map[string]string{
	"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#",
}

// Key transposes a key such as "G", "Bb" or "F#m" by semitones (negative goes
// down). Flats come back as sharps; the minor suffix is kept.
func Key(key string, semitones int) (string, error) {
	root, minor := key, ""
	if strings.HasSuffix(key, "m") {
		root, minor = strings.TrimSuffix(key, "m"), "m"
	}
	if sharp, ok := flatToSharp[root]; ok {
		root = sharp
	}
	idx := -1
	for i, n := range sharps {
		if n == root {
			idx = i
		}
	}
	if idx < 0 {
		return "", fmt.Errorf("unknown key %q", key)
	}
	next := ((idx+semitones)%12 + 12) % 12
	return sharps[next] + minor, nil
}
