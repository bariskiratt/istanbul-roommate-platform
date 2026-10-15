import type { ReceivedLike } from "./api";

/**
 * Beğeniler kuyruğu KİŞİLERİ listeler, kaydırmaları değil.
 *
 * Sunucu satır başına bir beğeni döndürüyor (GET /api/swipes/received, en
 * yeni önce). Eskiden ekran bunları tek tek gösteriyordu: üç ilanını beğenen
 * kişi kuyrukta üç kez çıkıyordu. Burada kişiye göre toplanır; kişinin sırası
 * en yeni beğenisinin sırasıdır. Karar da kişiye verilir: sunucu, kartın
 * swipeId'siyle gelen kararı o kişinin bütün bekleyen beğenilerine uygular
 * (backend/app/swipes.py respond_to_like).
 */
export interface LikeGroup {
  user: ReceivedLike["user"];
  /** Bu kişinin bekleyen beğenileri, en yeni önce. */
  likes: ReceivedLike[];
  /** Karar bu beğeni üzerinden gönderilir (en yenisi). */
  swipeId: number;
}

export const groupLikesByPerson = (likes: ReceivedLike[]): LikeGroup[] => {
  const groups = new Map<number, LikeGroup>();
  for (const like of likes) {
    const group = groups.get(like.user.id);
    if (group) {
      group.likes.push(like);
    } else {
      groups.set(like.user.id, { user: like.user, likes: [like], swipeId: like.swipe_id });
    }
  }
  return [...groups.values()];
};
