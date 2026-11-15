package song

import "testing"

func TestValidate(t *testing.T) {
	cases := []struct {
		name    string
		song    Song
		wantErr bool
	}{
		{"ok", Song{Title: "Amazing Grace", Key: "G", BPM: 72}, false},
		{"no title", Song{Key: "G", BPM: 72}, true},
		{"blank title", Song{Title: "  ", Key: "G", BPM: 72}, true},
		{"no key", Song{Title: "Amazing Grace", BPM: 72}, true},
		{"bpm too low", Song{Title: "Amazing Grace", Key: "G", BPM: 10}, true},
		{"bpm too high", Song{Title: "Amazing Grace", Key: "G", BPM: 400}, true},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if err := c.song.Validate(); (err != nil) != c.wantErr {
				t.Fatalf("Validate() error = %v, wantErr %v", err, c.wantErr)
			}
		})
	}
}
