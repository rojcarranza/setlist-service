// Package store keeps setlists in memory; a restart starts from the seed.
package store

import (
	"sort"
	"sync"

	"github.com/rojcarranza/setlist-service/setlist"
	"github.com/rojcarranza/setlist-service/song"
)

// Store is a concurrency-safe in-memory setlist store.
type Store struct {
	mu   sync.RWMutex
	byID map[string]setlist.Setlist
}

// New returns a store holding the seed setlists.
func New() *Store {
	s := &Store{byID: map[string]setlist.Setlist{}}
	s.Put(setlist.Setlist{ID: "sunday", Name: "Sunday morning", Date: "2026-11-15", Songs: []song.Song{
		{ID: "s1", Title: "Amazing Grace", Artist: "Traditional", Key: "G", BPM: 72},
		{ID: "s2", Title: "How Great Thou Art", Artist: "Traditional", Key: "C", BPM: 66},
		{ID: "s3", Title: "10,000 Reasons", Artist: "Matt Redman", Key: "G", BPM: 73},
	}})
	s.Put(setlist.Setlist{ID: "youth", Name: "Youth night", Date: "2026-11-20", Songs: []song.Song{
		{ID: "y1", Title: "Oceans", Artist: "Hillsong United", Key: "D", BPM: 66},
		{ID: "y2", Title: "What a Beautiful Name", Artist: "Hillsong Worship", Key: "D", BPM: 68},
	}})
	return s
}

// Put inserts or replaces a setlist.
func (s *Store) Put(sl setlist.Setlist) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.byID[sl.ID] = sl
}

// Get returns the setlist with this id.
func (s *Store) Get(id string) (setlist.Setlist, bool) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	sl, ok := s.byID[id]
	return sl, ok
}

// List returns every setlist ordered by date.
func (s *Store) List() []setlist.Setlist {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]setlist.Setlist, 0, len(s.byID))
	for _, sl := range s.byID {
		out = append(out, sl)
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Date < out[j].Date })
	return out
}
