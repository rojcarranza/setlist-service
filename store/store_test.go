package store

import "testing"

func TestSeedIsOrderedByDate(t *testing.T) {
	got := New().List()
	if len(got) != 2 || got[0].ID != "sunday" || got[1].ID != "youth" {
		t.Fatalf("List() = %+v", got)
	}
}

func TestGetMissing(t *testing.T) {
	if _, ok := New().Get("nope"); ok {
		t.Fatal("found a setlist that does not exist")
	}
}
