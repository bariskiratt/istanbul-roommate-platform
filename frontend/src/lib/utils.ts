import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Fotoğrafı olmayan kullanıcının avatarındaki baş harfler:
 * "Ayşe Yılmaz" -> "AY", "ilker" -> "İ", boş ad -> "".
 * Büyük harf Türkçe kuralıyla yapılır (i -> İ); kullanıcıların çoğu Türk.
 */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "";
  // Array.from harfi kod noktası olarak alır; emoji gibi iki birimlik
  // karakterler ortadan bölünmez.
  const first = Array.from(words[0])[0];
  const last = words.length > 1 ? Array.from(words[words.length - 1])[0] : "";
  return (first + last).toLocaleUpperCase("tr-TR");
}
