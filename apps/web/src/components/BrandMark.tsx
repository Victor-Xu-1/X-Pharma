import { PRODUCT_LOGO_URL } from "../lib/product";

/** Adjacent product text names the logo; the image must not repeat that name. */
export function BrandMark() {
  return (
    <span className="brand-symbol" aria-hidden="true">
      <img className="brand-image" src={PRODUCT_LOGO_URL} alt="" width={128} height={128} decoding="async" />
    </span>
  );
}
