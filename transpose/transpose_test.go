package transpose

import "testing"

func TestKey(t *testing.T) {
	cases := []struct {
		key  string
		by   int
		want string
	}{
		{"G", 5, "C"},
		{"G", 2, "A"},
		{"C", 7, "G"},
		{"A", 3, "C"},
		{"B", 1, "C"},
		{"C", -1, "B"},
		{"Bb", 2, "C"},
		{"F#m", 2, "G#m"},
		{"Em", 0, "Em"},
		{"D", 12, "D"},
		{"D", -14, "C"},
	}
	for _, c := range cases {
		t.Run(c.key, func(t *testing.T) {
			got, err := Key(c.key, c.by)
			if err != nil {
				t.Fatal(err)
			}
			if got != c.want {
				t.Fatalf("Key(%q, %d) = %q, want %q", c.key, c.by, got, c.want)
			}
		})
	}
}

func TestKeyUnknown(t *testing.T) {
	if _, err := Key("H", 1); err == nil {
		t.Fatal("expected an error for an unknown key")
	}
}

func TestCapoMatchesTranspose(t *testing.T) {
	// A capo on fret 5 plays G chord shapes in C.
	got, _ := Key("G", 5)
	if got != "C" {
		t.Fatalf("capo 5 on G = %q, want C", got)
	}
}
