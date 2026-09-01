import { Icon } from "./Icon";

export function BrandLogo({ size = 40 }: { size?: number }) {
  return (
    <span className="brand-logo" style={{ width: size, height: size }} aria-hidden="true">
      <Icon name="layers" size={Math.round(size * 0.55)} style={{ color: "#fff" }} />
    </span>
  );
}
