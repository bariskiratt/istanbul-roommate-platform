import { useState } from "react";
import { toast } from "sonner";
import { uploadPhoto } from "@/lib/api";
import { useI18n } from "@/i18n";

/**
 * Dosya seçtirip backend'e yükler; başarılı olunca URL'yi geri verir.
 * Kullanım: const { pick, uploading } = usePhotoUpload(url => setPhotos(p => [...p, url]));
 */
export function usePhotoUpload(onUploaded: (url: string) => void) {
  const [uploading, setUploading] = useState(false);
  const { t } = useI18n();

  const pick = () => {
    if (uploading) return;
    const input = document.createElement("input");
    input.type = "file";
    input.accept = "image/jpeg,image/png,image/webp";
    input.onchange = async () => {
      const file = input.files?.[0];
      if (!file) return;
      setUploading(true);
      try {
        const { url } = await uploadPhoto(file);
        onUploaded(url);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : t("common.photoUploadFailed"));
      } finally {
        setUploading(false);
      }
    };
    input.click();
  };

  return { pick, uploading };
}
