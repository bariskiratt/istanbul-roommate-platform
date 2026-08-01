import { useState } from "react";
import { toast } from "sonner";
import { uploadPhoto } from "@/lib/api";
import { useI18n } from "@/i18n";

/**
 * Dosya seçtirip backend'e yükler; başarılı olunca URL'yi geri verir.
 * Kullanım: const { pick, uploading } = usePhotoUpload(url => setPhotos(p => [...p, url]));
 *
 * `error`, son yüklemenin hata metnidir (toast kaybolduktan sonra da formda
 * gösterilebilsin diye tutulur). Yeni bir yükleme başlayınca temizlenir;
 * `uploading` her durumda false'a döner, yani hata kullanıcıyı kilitlemez.
 *
 * ÇOKLU SEÇİM: ilan için en az 3 fotoğraf isteniyor; tek seçimde kullanıcı
 * üç ayrı dosya penceresi açmak zorunda kalıyordu. `limit` ile bir seferde
 * kaç dosya kabul edileceği söylenir (kalan kota). Dosyalar SIRAYLA yüklenir:
 * paralel yükleme ücretsiz sunucuda hem zaman aşımına hem sıra karışmasına
 * yol açıyordu.
 */
export function usePhotoUpload(onUploaded: (url: string) => void) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { t } = useI18n();

  const pick = (limit = 1) => {
    if (uploading) return;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/jpeg,image/png,image/webp";
    input.multiple = limit > 1;
    input.onchange = async () => {
      const files = Array.from(input.files ?? []).slice(0, Math.max(1, limit));
      if (files.length === 0) return;
      setUploading(true);
      setError(null);
      try {
        for (const file of files) {
          const { url } = await uploadPhoto(file);
          onUploaded(url);
        }
      } catch (err) {
        // Kısmi başarı korunur: hatadan önce yüklenenler zaten eklendi.
        const message = err instanceof Error ? err.message : t("common.photoUploadFailed");
        setError(message);
        toast.error(message);
      } finally {
        setUploading(false);
      }
    };
    input.click();
  };

  return { pick, uploading, error, clearError: () => setError(null) };
}
