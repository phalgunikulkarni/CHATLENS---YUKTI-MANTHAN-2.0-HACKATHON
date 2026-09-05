import { useEffect, useState } from "react";
import { apiService } from "../api/client";

interface Props extends React.ImgHTMLAttributes<HTMLImageElement> {
  src: string;
}

/** Loads backend images through the authenticated API adapter, then cleans up the object URL. */
export function ProtectedImage({ src, ...props }: Props) {
  const [objectUrl, setObjectUrl] = useState<string>();
  const inlineSource = src.startsWith("data:") || src.startsWith("blob:");

  useEffect(() => {
    if (inlineSource) {
      setObjectUrl(undefined);
      return;
    }

    let active = true;
    let loadedUrl: string | undefined;
    setObjectUrl(undefined);

    apiService.getImageBlob(src)
      .then((blob) => {
        const nextUrl = URL.createObjectURL(blob);
        if (!active) {
          URL.revokeObjectURL(nextUrl);
          return;
        }
        loadedUrl = nextUrl;
        setObjectUrl(nextUrl);
      })
      .catch(() => {
        if (active) setObjectUrl(undefined);
      });

    return () => {
      active = false;
      if (loadedUrl) URL.revokeObjectURL(loadedUrl);
    };
  }, [inlineSource, src]);

  return <img {...props} src={inlineSource ? src : objectUrl} />;
}