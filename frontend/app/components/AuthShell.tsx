import Image from "next/image";
import type { FormEvent, ReactNode } from "react";

/** Login e definição de senha: o painel pintado da landing ao lado do formulário. */
export function AuthShell({
  title,
  onSubmit,
  children
}: {
  title: string;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  children: ReactNode;
}) {
  return (
    <div className="authShell">
      <div className="authArt" aria-hidden="true">
        <p className="authArtLine">
          Menos operação.
          <br />
          Mais advocacia.
        </p>
      </div>
      <main className="authMain">
        <form className="authCard" onSubmit={onSubmit}>
          <div className="authBrand">
            <Image
              className="brandAssetDark"
              src="/brand/causor-lockup-dark.png"
              alt="Causor"
              width={137}
              height={26}
              unoptimized
              priority
            />
            <Image
              className="brandAssetLight"
              src="/brand/causor-lockup-light.png"
              alt="Causor"
              width={137}
              height={26}
              unoptimized
              priority
            />
          </div>
          <h1 className="authTitle">{title}</h1>
          {children}
        </form>
      </main>
    </div>
  );
}
