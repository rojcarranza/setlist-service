package share

import (
	"context"
	"testing"
	"time"

	"github.com/rojcarranza/setlist-service/setlist"
)

func TestLinkIsStable(t *testing.T) {
	sl := setlist.Setlist{ID: "sun", Name: "Sunday", Date: "2026-11-15"}
	if Link(sl) != Link(sl) {
		t.Fatal("link changed between calls")
	}
	other := setlist.Setlist{ID: "wed", Name: "Wednesday", Date: "2026-11-18"}
	if Link(sl) == Link(other) {
		t.Fatal("two setlists share a link")
	}
}

func TestSetlistNotifiesInTime(t *testing.T) {
	link, err := Setlist(context.Background(), setlist.Setlist{ID: "sun"}, DelayNotifier{Delay: time.Millisecond}, time.Second)
	if err != nil || link == "" {
		t.Fatalf("link=%q err=%v", link, err)
	}
}

func TestSetlistTimesOut(t *testing.T) {
	_, err := Setlist(context.Background(), setlist.Setlist{ID: "sun"}, DelayNotifier{Delay: time.Second}, 10*time.Millisecond)
	if err == nil {
		t.Fatal("expected a timeout")
	}
}
