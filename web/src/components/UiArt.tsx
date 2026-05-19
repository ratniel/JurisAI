import type { SVGProps } from 'react'

type IconName =
  | 'attach'
  | 'bell'
  | 'bookmark'
  | 'chat'
  | 'document'
  | 'grid'
  | 'help'
  | 'history'
  | 'layers'
  | 'menu'
  | 'microphone'
  | 'moon'
  | 'plus'
  | 'save'
  | 'schemes'
  | 'search'
  | 'send'
  | 'settings'
  | 'spark'
  | 'sun'
  | 'target'
  | 'user'
  | 'bolt'
  | 'shield'
  | 'external'

type UiIconProps = SVGProps<SVGSVGElement> & {
  name: IconName
}

export function UiIcon({ name, ...props }: UiIconProps) {
  return (
    <svg
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth="1.8"
      viewBox="0 0 24 24"
      {...props}
    >
      {name === 'attach' ? (
        <path d="M16.5 6.75 9 14.25a3.25 3.25 0 1 0 4.6 4.6l8.1-8.1a5.5 5.5 0 0 0-7.78-7.78l-8.4 8.4a7.75 7.75 0 1 0 10.96 10.96L18 20.82" />
      ) : null}
      {name === 'bell' ? (
        <>
          <path d="M6.5 9a5.5 5.5 0 1 1 11 0c0 5 2 6.5 2 6.5H4.5S6.5 14 6.5 9" />
          <path d="M10 19a2.3 2.3 0 0 0 4 0" />
        </>
      ) : null}
      {name === 'bookmark' ? (
        <path d="M7 4.75h10v14.5L12 15.5 7 19.25Z" />
      ) : null}
      {name === 'chat' ? (
        <path d="M5.75 6.75h12.5a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2H11l-4.75 3v-3H5.75a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2Z" />
      ) : null}
      {name === 'document' ? (
        <>
          <path d="M7.5 3.75h6l4 4v12.5H7.5Z" />
          <path d="M13.5 3.75v4h4" />
          <path d="M10 12h5M10 15.5h5" />
        </>
      ) : null}
      {name === 'external' ? (
        <>
          <path d="M14 5h5v5" />
          <path d="M10 14 19 5" />
          <path d="M19 13v5H5V6h5" />
        </>
      ) : null}
      {name === 'grid' ? (
        <>
          <rect x="4" y="4" width="7" height="7" rx="1.5" />
          <rect x="13" y="4" width="7" height="7" rx="1.5" />
          <rect x="4" y="13" width="7" height="7" rx="1.5" />
          <rect x="13" y="13" width="7" height="7" rx="1.5" />
        </>
      ) : null}
      {name === 'help' ? (
        <>
          <circle cx="12" cy="12" r="8.25" />
          <path d="M9.75 9.25a2.75 2.75 0 1 1 4.44 2.18c-.94.7-1.69 1.27-1.69 2.57" />
          <path d="M12 16.5h.01" />
        </>
      ) : null}
      {name === 'history' ? (
        <>
          <path d="M4.75 12A7.25 7.25 0 1 0 7 6.9" />
          <path d="M4.75 4.75v4.5h4.5" />
          <path d="M12 8.5V12l2.5 1.75" />
        </>
      ) : null}
      {name === 'layers' ? (
        <>
          <path d="m12 4 8 4.5-8 4.5-8-4.5Z" />
          <path d="m5 12 7 4 7-4" />
          <path d="m5 15.5 7 4 7-4" />
        </>
      ) : null}
      {name === 'menu' ? (
        <>
          <path d="M5 7.5h14" />
          <path d="M5 12h14" />
          <path d="M5 16.5h14" />
        </>
      ) : null}
      {name === 'microphone' ? (
        <>
          <rect x="9" y="4" width="6" height="10" rx="3" />
          <path d="M6.5 11.5a5.5 5.5 0 0 0 11 0" />
          <path d="M12 17v3" />
        </>
      ) : null}
      {name === 'moon' ? (
        <path d="M15.5 3.75a7.95 7.95 0 1 0 4.75 13.95A8.7 8.7 0 1 1 15.5 3.75Z" />
      ) : null}
      {name === 'plus' ? (
        <>
          <path d="M12 5v14" />
          <path d="M5 12h14" />
        </>
      ) : null}
      {name === 'save' ? (
        <>
          <path d="M6.5 4.75h11l1.75 1.75v12.75H4.75V4.75Z" />
          <path d="M8 4.75v5h7v-5" />
          <path d="M8.5 15.25h7" />
        </>
      ) : null}
      {name === 'schemes' ? (
        <>
          <path d="M5.5 8.5 12 4l6.5 4.5v7L12 20l-6.5-4.5Z" />
          <path d="M9.5 10.25h5" />
          <path d="M9.5 13h5" />
        </>
      ) : null}
      {name === 'search' ? (
        <>
          <circle cx="10.5" cy="10.5" r="5.5" />
          <path d="m15 15 4.25 4.25" />
        </>
      ) : null}
      {name === 'send' ? (
        <path d="m5 12 13.5-7-3 14-4.75-5.25L5 12Z" />
      ) : null}
      {name === 'settings' ? (
        <>
          <circle cx="12" cy="12" r="2.8" />
          <path d="m12 4.5 1.15 1.7 2.03.33.9 1.86 1.94.66v2.1l-1.94.66-.9 1.86-2.03.33L12 19.5l-1.15-1.7-2.03-.33-.9-1.86-1.94-.66v-2.1l1.94-.66.9-1.86 2.03-.33Z" />
        </>
      ) : null}
      {name === 'spark' ? (
        <>
          <path d="m12 3.5 1.7 4.8L18.5 10l-4.8 1.7L12 16.5l-1.7-4.8L5.5 10l4.8-1.7Z" />
          <path d="m18.5 4.5.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8Z" />
        </>
      ) : null}
      {name === 'sun' ? (
        <>
          <circle cx="12" cy="12" r="3.75" />
          <path d="M12 2.75v2.5M12 18.75v2.5M21.25 12h-2.5M5.25 12h-2.5M18.54 5.46l-1.77 1.77M7.23 16.77l-1.77 1.77M18.54 18.54l-1.77-1.77M7.23 7.23 5.46 5.46" />
        </>
      ) : null}
      {name === 'target' ? (
        <>
          <circle cx="12" cy="12" r="7.5" />
          <circle cx="12" cy="12" r="3.5" />
          <path d="M12 2.75v2.5M21.25 12h-2.5M12 18.75v2.5M5.25 12h-2.5" />
        </>
      ) : null}
      {name === 'user' ? (
        <>
          <circle cx="12" cy="8.25" r="3.25" />
          <path d="M5.5 19.25a6.5 6.5 0 0 1 13 0" />
        </>
      ) : null}
      {name === 'bolt' ? (
        <path d="M13.75 2.75 6.5 13.1h4.75l-1 8.15L17.5 10.9h-4.75Z" />
      ) : null}
      {name === 'shield' ? (
        <>
          <path d="M12 3.75 18.25 6v5.25c0 4.1-2.7 7.86-6.25 9-3.55-1.14-6.25-4.9-6.25-9V6Z" />
          <path d="M9.25 12.25 11 14l3.75-4" />
        </>
      ) : null}
    </svg>
  )
}

export function BrandCrest(props: SVGProps<SVGSVGElement>) {
  return (
    <svg fill="none" viewBox="0 0 64 64" {...props}>
      <path
        d="M32 5.5 50.5 11v15.5c0 12.7-7.5 24.17-18.5 28C21 50.67 13.5 39.2 13.5 26.5V11Z"
        stroke="currentColor"
        strokeWidth="2"
      />
      <path d="M22 24h20M24 18h16M26 30h12" stroke="currentColor" strokeWidth="2" />
      <path d="M24.5 16.5v18M32 16.5v18M39.5 16.5v18" stroke="currentColor" strokeWidth="1.8" />
      <path d="M20 36h24" stroke="currentColor" strokeWidth="2" />
    </svg>
  )
}

export function InstitutionIllustration(props: SVGProps<SVGSVGElement>) {
  return (
    <svg fill="none" viewBox="0 0 420 320" {...props}>
      <circle cx="210" cy="160" r="138" stroke="currentColor" strokeOpacity=".12" />
      <circle cx="210" cy="160" r="118" stroke="currentColor" strokeOpacity=".08" />
      <path
        d="M112 234h196M145 218h130M162 115h96M171 203v-43M196 203v-43M224 203v-43M249 203v-43"
        stroke="currentColor"
        strokeOpacity=".52"
        strokeWidth="2.5"
      />
      <path
        d="M150 152c0-34.24 27.76-62 62-62s62 27.76 62 62"
        stroke="currentColor"
        strokeOpacity=".62"
        strokeWidth="3"
      />
      <path
        d="M147 154h126M158 144h104"
        stroke="currentColor"
        strokeOpacity=".4"
        strokeWidth="2"
      />
      <path
        d="M194 86V58m0 0 10 5m-10-5-10 5"
        stroke="currentColor"
        strokeOpacity=".9"
        strokeWidth="2.25"
      />
      <path d="M179 74h30" stroke="currentColor" strokeOpacity=".74" strokeWidth="2" />
      <path d="M102 182h42v44M318 182h-42v44" stroke="currentColor" strokeOpacity=".12" strokeWidth="2" />
    </svg>
  )
}
