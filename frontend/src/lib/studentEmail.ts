/**
 * Kayıt formundaki anlık "üniversite adresi mi" kontrolü.
 *
 * Asıl karar sunucuda (backend/app/auth.py is_student_email); bu yalnızca
 * kullanıcıya formu göndermeden önce ipucu verir. Ama ikisi ayrışırsa
 * istemci sunucunun kabul ettiği adresi kapıda bırakır: eskiden burada
 * `email.includes(".edu.tr")` vardı ve Sabancı öğrencileri
 * (@sabanciuniv.edu) "devam" düğmesini hiç açamıyordu.
 *
 * Sunucunun kuralı: alan adı edu.tr ile biter YA DA bilinen üniversite
 * alan adlarından biri (ya da alt alanı). Bilinen listenin .edu.tr OLMAYAN
 * kısmı aşağıda; backend/app/universities.py ile eşitliği
 * src/test/studentEmail.test.ts denetler.
 */
export const NON_EDU_TR_UNIVERSITY_DOMAINS: readonly string[] = ["sabanciuniv.edu"];

/** Adresin @'ten sonraki kısmı, küçük harfle; @ yoksa boş. */
const domainOf = (email: string): string => {
  const at = email.lastIndexOf("@");
  return at < 0 ? "" : email.slice(at + 1).trim().toLowerCase();
};

const matchesDomain = (domain: string, known: string) =>
  domain === known || domain.endsWith("." + known);

export const isStudentEmail = (email: string): boolean => {
  const domain = domainOf(email);
  if (!domain) return false;
  if (matchesDomain(domain, "edu.tr")) return true;
  return NON_EDU_TR_UNIVERSITY_DOMAINS.some(known => matchesDomain(domain, known));
};
