// Package setlist is an ordered list of songs for one service.
package setlist

import (
	"fmt"

	"github.com/rojcarranza/setlist-service/song"
	"github.com/rojcarranza/setlist-service/transpose"
)

// Setlist is the songs a team plays at one service, in order.
type Setlist struct {
	ID    string      `json:"id"`
	Name  string      `json:"name"`
	Date  string      `json:"date"`
	Songs []song.Song `json:"songs"`
}

// Add appends a valid song.
func (s *Setlist) Add(sg song.Song) error {
	if err := sg.Validate(); err != nil {
		return err
	}
	s.Songs = append(s.Songs, sg)
	return nil
}

// Remove drops the song with this id.
func (s *Setlist) Remove(id string) error {
	for i, sg := range s.Songs {
		if sg.ID == id {
			s.Songs = append(s.Songs[:i], s.Songs[i+1:]...)
			return nil
		}
	}
	return fmt.Errorf("no song %q in setlist %q", id, s.Name)
}

// Transposed returns a copy with every song moved by semitones.
func (s Setlist) Transposed(semitones int) (Setlist, error) {
	out := s
	out.Songs = make([]song.Song, len(s.Songs))
	for i, sg := range s.Songs {
		k, err := transpose.Key(sg.Key, semitones)
		if err != nil {
			return Setlist{}, fmt.Errorf("song %q: %w", sg.Title, err)
		}
		sg.Key = k
		out.Songs[i] = sg
	}
	return out, nil
}
