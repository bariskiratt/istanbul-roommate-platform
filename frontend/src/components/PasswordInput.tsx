import { useState, forwardRef } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";

type Props = React.InputHTMLAttributes<HTMLInputElement>;

/**
 * Göster/gizle düğmeli şifre alanı.
 * - onMouseDown preventDefault: düğmeye tıklayınca input odağı kaybolmaz.
 * - z-10 + geniş sağ boşluk: Safari'nin kendi otomatik doldurma simgesiyle
 *   çakışmayı önler.
 */
const PasswordInput = forwardRef<HTMLInputElement, Props>(
  ({ className, ...props }, ref) => {
    const [show, setShow] = useState(false);
    return (
      <div className="relative">
        <Input
          ref={ref}
          type={show ? "text" : "password"}
          autoComplete="new-password"
          {...props}
          className={`pr-12 ${className ?? ""}`}
        />
        <button
          type="button"
          tabIndex={-1}
          aria-label={show ? "Şifreyi gizle" : "Şifreyi göster"}
          onMouseDown={e => e.preventDefault()}
          onClick={() => setShow(v => !v)}
          className="absolute right-4 top-1/2 -translate-y-1/2 z-10 p-1 text-muted-foreground hover:text-foreground transition-colors"
        >
          {show ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
        </button>
      </div>
    );
  },
);
PasswordInput.displayName = "PasswordInput";

export default PasswordInput;
