package setlist

import (
	"testing"

	"github.com/rojcarranza/setlist-service/song"
)

func sample() Setlist {
	return Setlist{ID: "sun", Name: "Sunday morning", Songs: []song.Song{
		{ID: "1", Title: "Amazing Grace", Key: "G", BPM: 72},
		{ID: "2", Title: "How Great Thou Art", Key: "C", BPM: 66},
	}}
}

func TestAddRejectsInvalidSong(t *testing.T) {
	s := sample()
	if err := s.Add(song.Song{Title: "No key", BPM: 80}); err == nil {
		t.Fatal("expected an error")
	}
	if len(s.Songs) != 2 {
		t.Fatalf("songs = %d, want 2", len(s.Songs))
	}
}

func TestAddAppends(t *testing.T) {
	s := sample()
	if err := s.Add(song.Song{ID: "3", Title: "10,000 Reasons", Key: "G", BPM: 73}); err != nil {
		t.Fatal(err)
	}
	if got := s.Songs[2].Title; got != "10,000 Reasons" {
		t.Fatalf("last song = %q", got)
	}
}

func TestRemove(t *testing.T) {
	s := sample()
	if err := s.Remove("1"); err != nil {
		t.Fatal(err)
	}
	if len(s.Songs) != 1 || s.Songs[0].ID != "2" {
		t.Fatalf("songs = %+v", s.Songs)
	}
	if err := s.Remove("nope"); err == nil {
		t.Fatal("expected an error for a missing song")
	}
}

func TestTransposedMovesEverySong(t *testing.T) {
	got, err := sample().Transposed(5)
	if err != nil {
		t.Fatal(err)
	}
	want := []string{"C", "F"}
	for i, k := range want {
		if got.Songs[i].Key != k {
			t.Errorf("song %d key = %q, want %q", i, got.Songs[i].Key, k)
		}
	}
}

func TestTransposedLeavesOriginal(t *testing.T) {
	s := sample()
	if _, err := s.Transposed(2); err != nil {
		t.Fatal(err)
	}
	if s.Songs[0].Key != "G" {
		t.Fatalf("original changed to %q", s.Songs[0].Key)
	}
}
