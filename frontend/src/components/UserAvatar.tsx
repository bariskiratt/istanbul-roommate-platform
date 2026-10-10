import { User as UserIcon } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn, initials } from "@/lib/utils";

interface UserAvatarProps {
  name: string;
  photo?: string | null;
  /** Boyut, kenarlık ve baş harflerin yazı boyutu (ör. "w-14 h-14 text-lg"). */
  className?: string;
  imageClassName?: string;
}

/**
 * Kullanıcının fotoğrafı; yoksa ya da yüklenemezse adının baş harfleri.
 *
 * Eskiden fotoğrafsız herkes için api.dicebear.com'dan bir resim çekiliyordu:
 * her sayfa açılışında dış bir siteye istek gidiyor ve o site CSP'de açık
 * tutulmak zorunda kalıyordu. Baş harfler tarayıcıda üretilir, dışarıya istek
 * gitmez. Ad da bilinmiyorsa genel bir kişi simgesi basılır.
 */
const UserAvatar = ({ name, photo, className, imageClassName }: UserAvatarProps) => {
  const text = initials(name);
  return (
    <Avatar className={className}>
      {photo && <AvatarImage src={photo} alt="" className={cn("object-cover", imageClassName)} />}
      {/* Fotoğraf varken baş harfler hemen basılmaz: hızlı yüklenen bir
          fotoğrafın önünde kısa bir harf titremesi görünmesin. */}
      <AvatarFallback delayMs={photo ? 400 : undefined} className="bg-lavender/60 font-semibold text-foreground">
        {text || <UserIcon className="w-1/2 h-1/2 text-muted-foreground" />}
      </AvatarFallback>
    </Avatar>
  );
};

export default UserAvatar;
