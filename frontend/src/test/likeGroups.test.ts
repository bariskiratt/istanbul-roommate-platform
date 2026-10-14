import { describe, expect, it } from "vitest";
import type { ReceivedLike } from "@/lib/api";
import { groupLikesByPerson } from "@/lib/likeGroups";

const person = (id: number) => ({
  id,
  name: `Kişi ${id}`,
  university: null,
  department: null,
  year: null,
  budget_min: null,
  budget_max: null,
  smoking: null,
  pets: null,
  alcohol: null,
  sleep_schedule: null,
  preferred_districts: [],
  bio: "",
  photos: [],
});

const like = (swipeId: number, userId: number, listingId: number): ReceivedLike => ({
  swipe_id: swipeId,
  user: person(userId),
  listing_id: listingId,
  listing_title: `İlan ${listingId}`,
  target: null,
  comment: null,
  created_at: "2026-10-14T10:00:00",
});

describe("groupLikesByPerson", () => {
  it("aynı kişinin beğenileri tek grupta, kişi sırası en yeni beğenisine göre", () => {
    // Sunucu en yeni önce döndürür.
    const groups = groupLikesByPerson([
      like(9, 1, 30),
      like(8, 2, 30),
      like(7, 1, 20),
      like(6, 1, 10),
    ]);
    expect(groups.map(g => g.user.id)).toEqual([1, 2]);
    expect(groups[0].likes.map(l => l.listing_id)).toEqual([30, 20, 10]);
    expect(groups[0].swipeId).toBe(9);
    expect(groups[1].likes).toHaveLength(1);
  });

  it("boş kuyruk", () => {
    expect(groupLikesByPerson([])).toEqual([]);
  });
});
