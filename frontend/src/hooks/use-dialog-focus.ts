import { useEffect, type RefObject } from "react";

/**
 * Elle kurulmuş modal paneller (ReportDialog, LikeComposer) için odak düzeni:
 * açılınca odağı `initialFocusRef`e verir, kapanınca açan öğeye geri döner;
 * Esc paneli kapatır, Tab panelin içinde döner (basit tuzak).
 *
 * Paneller Radix Dialog yerine elle kurulu, çünkü kaydırma kartının içinden
 * açılıyorlar ve kendi animasyonlarını taşıyorlar; erişilebilirliğin bu kısmı
 * da bu yüzden burada.
 */
export const useDialogFocus = (
  open: boolean,
  onClose: () => void,
  panelRef: RefObject<HTMLElement>,
  initialFocusRef: RefObject<HTMLElement>,
) => {
  useEffect(() => {
    if (!open) return;
    // Kapanışta odağı çağıran düğmeye geri veririz (klavye kullanıcısı
    // listenin/başlığın başına fırlamasın).
    const returnTo = document.activeElement as HTMLElement | null;
    // Panel çizildikten sonra odağı ilk öğeye al.
    const id = window.setTimeout(() => initialFocusRef.current?.focus(), 0);
    return () => {
      window.clearTimeout(id);
      returnTo?.focus?.();
    };
  }, [open, initialFocusRef]);

  useEffect(() => {
    if (!open) return;
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panelRef.current) return;
      const focusables = panelRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), textarea, [href], input, select, [tabindex]:not([tabindex="-1"])',
      );
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      const active = document.activeElement;
      if (e.shiftKey && (active === first || !panelRef.current.contains(active))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKeyDown, true);
    return () => document.removeEventListener("keydown", onKeyDown, true);
  }, [open, onClose, panelRef]);
};
