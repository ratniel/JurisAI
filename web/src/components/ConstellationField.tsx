import { useEffect, useRef } from 'react'
import { motion, useMotionValue, useSpring, useTransform } from 'motion/react'
import '../styles/constellation.css'

const nodes = [
  { id: 'a', x: 58, y: 80, label: 'Eligibility', side: 'left' },
  { id: 'b', x: 178, y: 45, label: 'State', side: 'left' },
  { id: 'c', x: 248, y: 154, label: 'Benefits', side: 'left' },
  { id: 'd', x: 106, y: 246, label: 'Schemes', side: 'left' },
  { id: 'e', x: 198, y: 326, label: 'Support', side: 'left' },
  { id: 'f', x: 116, y: 422, label: 'Access', side: 'left' },
  { id: 'g', x: 1160, y: 72, label: 'Farmers', side: 'right' },
  { id: 'h', x: 1284, y: 145, label: 'Housing', side: 'right' },
  { id: 'i', x: 1176, y: 226, label: 'Women', side: 'right' },
  { id: 'j', x: 1305, y: 310, label: 'Pensions', side: 'right' },
  { id: 'k', x: 1184, y: 384, label: 'Health', side: 'right' },
  { id: 'l', x: 1306, y: 454, label: 'Education', side: 'right' },
] as const

const edges = [
  { from: 'a', to: 'b', cp1: [100, 58], cp2: [130, 47] },
  { from: 'a', to: 'c', cp1: [96, 126], cp2: [156, 155] },
  { from: 'b', to: 'c', cp1: [210, 75], cp2: [230, 111] },
  { from: 'c', to: 'd', cp1: [213, 202], cp2: [160, 231] },
  { from: 'd', to: 'e', cp1: [130, 281], cp2: [161, 310] },
  { from: 'e', to: 'f', cp1: [157, 351], cp2: [127, 386] },
  { from: 'g', to: 'h', cp1: [1210, 68], cp2: [1247, 100] },
  { from: 'g', to: 'i', cp1: [1162, 130], cp2: [1168, 177] },
  { from: 'h', to: 'i', cp1: [1251, 180], cp2: [1216, 207] },
  { from: 'i', to: 'j', cp1: [1224, 263], cp2: [1266, 290] },
  { from: 'j', to: 'k', cp1: [1268, 347], cp2: [1227, 373] },
  { from: 'k', to: 'l', cp1: [1225, 411], cp2: [1268, 437] },
] as const

type Offset = { x: number; y: number }
type ConstellationNode = (typeof nodes)[number]

const zeroOffsets = Object.fromEntries(nodes.map(({ id }) => [id, { x: 0, y: 0 }])) as Record<
  string,
  Offset
>

function format(value: number) {
  return value.toFixed(2)
}

function getPathData(
  edge: (typeof edges)[number],
  offsets: Record<string, Offset>,
) {
  const start = nodes.find((node) => node.id === edge.from) as ConstellationNode
  const end = nodes.find((node) => node.id === edge.to) as ConstellationNode
  const startOffset = offsets[start.id]
  const endOffset = offsets[end.id]
  const [cp1x, cp1y] = edge.cp1
  const [cp2x, cp2y] = edge.cp2
  const control1x = cp1x + startOffset.x * (2 / 3) + endOffset.x * (1 / 3)
  const control1y = cp1y + startOffset.y * (2 / 3) + endOffset.y * (1 / 3)
  const control2x = cp2x + startOffset.x * (1 / 3) + endOffset.x * (2 / 3)
  const control2y = cp2y + startOffset.y * (1 / 3) + endOffset.y * (2 / 3)

  return `M${format(start.x + startOffset.x)} ${format(start.y + startOffset.y)} C${format(control1x)} ${format(control1y)} ${format(control2x)} ${format(control2y)} ${format(end.x + endOffset.x)} ${format(end.y + endOffset.y)}`
}

/** Decorative, cursor-reactive legal-scheme constellation for the home hero. */
export function ConstellationField() {
  const fieldRef = useRef<HTMLDivElement>(null)
  const nodeRefs = useRef<Array<SVGGElement | null>>([])
  const nodeVisualRefs = useRef<Array<SVGCircleElement | null>>([])
  const labelRefs = useRef<Array<HTMLSpanElement | null>>([])
  const pathRefs = useRef<Array<SVGPathElement | null>>([])
  const pointerX = useMotionValue(0)
  const pointerY = useMotionValue(0)
  const smoothX = useSpring(pointerX, { stiffness: 320, damping: 30, mass: 0.24 })
  const smoothY = useSpring(pointerY, { stiffness: 320, damping: 30, mass: 0.24 })
  const parallaxX = useTransform(smoothX, [-1, 1], [15, -15])
  const parallaxY = useTransform(smoothY, [-1, 1], [11, -11])

  useEffect(() => {
    const currentField = fieldRef.current
    const currentHero = currentField?.parentElement
    if (!currentField || !currentHero) return
    const field = currentField
    const hero = currentHero

    const motionAllowed = window.matchMedia(
      '(hover: hover) and (pointer: fine) and (prefers-reduced-motion: no-preference)',
    )
    if (!motionAllowed.matches) return

    let previousPoint: { x: number; y: number; time: number } | null = null

    function resetField() {
      previousPoint = null
      pointerX.set(0)
      pointerY.set(0)
      field.style.setProperty('--pointer-x', '-1000px')
      field.style.setProperty('--pointer-y', '-1000px')
      field.style.setProperty('--pointer-active', '0')
      field.style.setProperty('--wind-angle', '0deg')
      field.style.setProperty('--wind-intensity', '0')
      nodeRefs.current.forEach((node) => {
        if (!node) return
        node.removeAttribute('transform')
        node.style.opacity = ''
      })
      nodeVisualRefs.current.forEach((node) => {
        if (node) node.style.transform = ''
      })
      labelRefs.current.forEach((label) => {
        if (!label) return
        label.style.removeProperty('--node-dx')
        label.style.removeProperty('--node-dy')
        label.style.opacity = ''
      })
      pathRefs.current.forEach((path, index) => {
        if (path) path.setAttribute('d', getPathData(edges[index], zeroOffsets))
      })
    }

    function handlePointerMove(event: PointerEvent) {
      if (event.pointerType !== 'mouse') return

      const heroBounds = hero.getBoundingClientRect()
      const insideHero =
        event.clientX >= heroBounds.left &&
        event.clientX <= heroBounds.right &&
        event.clientY >= heroBounds.top &&
        event.clientY <= heroBounds.bottom
      if (!insideHero) {
        resetField()
        return
      }

      const fieldBounds = field.getBoundingClientRect()
      const x = ((event.clientX - fieldBounds.left) / fieldBounds.width) * 1360
      const y = ((event.clientY - fieldBounds.top) / fieldBounds.height) * 500
      const now = performance.now()
      const heroX = ((event.clientX - heroBounds.left) / heroBounds.width) * 2 - 1
      const heroY = ((event.clientY - heroBounds.top) / heroBounds.height) * 2 - 1
      pointerX.set(heroX)
      pointerY.set(heroY)
      field.style.setProperty('--pointer-x', `${event.clientX - fieldBounds.left}px`)
      field.style.setProperty('--pointer-y', `${event.clientY - fieldBounds.top}px`)
      field.style.setProperty('--pointer-active', '1')

      const elapsed = previousPoint ? Math.max(8, now - previousPoint.time) : 16
      const velocityX = previousPoint ? (x - previousPoint.x) / elapsed : 0
      const velocityY = previousPoint ? (y - previousPoint.y) / elapsed : 0
      const speed = Math.hypot(velocityX, velocityY)
      const windX = speed ? velocityX / speed : 0
      const windY = speed ? velocityY / speed : 0
      const windAmount = Math.min(24, speed * 16)
      field.style.setProperty('--wind-angle', `${Math.atan2(velocityY, velocityX)}rad`)
      field.style.setProperty('--wind-intensity', `${Math.min(1, speed / 1.25)}`)
      previousPoint = { x, y, time: now }

      const offsets: Record<string, Offset> = {}
      nodes.forEach((node, index) => {
        const dx = node.x - x
        const dy = node.y - y
        const distance = Math.hypot(dx, dy)
        const influence = Math.max(0, 1 - distance / 390)
        const falloff = influence * influence
        const radialPush = falloff * 38
        const drift = windAmount * (0.12 + falloff * 0.88)
        const nodeX = dx / (distance || 1) * radialPush + windX * drift
        const nodeY = dy / (distance || 1) * radialPush + windY * drift
        offsets[node.id] = { x: nodeX, y: nodeY }

        const element = nodeRefs.current[index]
        if (!element) return
        element.setAttribute('transform', `translate(${format(nodeX)} ${format(nodeY)})`)
        element.style.opacity = `${0.7 + falloff * 0.3}`
        const visual = nodeVisualRefs.current[index]
        if (visual) visual.style.transform = `scale(${format(1 + falloff * 0.72)})`
        const label = labelRefs.current[index]
        if (label) {
          label.style.setProperty('--node-dx', `${format(nodeX * fieldBounds.width / 1360)}px`)
          label.style.setProperty('--node-dy', `${format(nodeY * fieldBounds.height / 500)}px`)
          label.style.opacity = `${0.48 + falloff * 0.42}`
        }
      })

      pathRefs.current.forEach((path, index) => {
        if (path) path.setAttribute('d', getPathData(edges[index], offsets))
      })
    }

    function handlePointerOut(event: PointerEvent) {
      if (event.relatedTarget instanceof Node && hero.contains(event.relatedTarget)) return
      resetField()
    }

    window.addEventListener('pointermove', handlePointerMove, { passive: true })
    window.addEventListener('pointerout', handlePointerOut)
    window.addEventListener('blur', resetField)
    return () => {
      window.removeEventListener('pointermove', handlePointerMove)
      window.removeEventListener('pointerout', handlePointerOut)
      window.removeEventListener('blur', resetField)
    }
  }, [pointerX, pointerY])

  return (
    <motion.div
      ref={fieldRef}
      className="constellation-field"
      aria-hidden="true"
      style={{ x: parallaxX, y: parallaxY }}
    >
      <svg className="constellation-svg" viewBox="0 0 1360 500" preserveAspectRatio="none" focusable="false">
        <g className="constellation-curves">
          {edges.map((edge, index) => (
            <path
              key={`${edge.from}-${edge.to}`}
              ref={(element) => { pathRefs.current[index] = element }}
              d={getPathData(edge, zeroOffsets)}
            />
          ))}
        </g>
        <g className="constellation-nodes">
          {nodes.map((node, index) => (
            <g
              className="constellation-node"
              key={node.id}
              ref={(element) => { nodeRefs.current[index] = element }}
            >
              <circle
                ref={(element) => { nodeVisualRefs.current[index] = element }}
                cx={node.x}
                cy={node.y}
                r={index % 3 === 0 ? 3.1 : 2.2}
              />
            </g>
          ))}
        </g>
      </svg>
      <div className="constellation-labels">
        {nodes.map((node, index) => (
          <span
            className={`constellation-label constellation-label-${node.side}`}
            key={node.id}
            ref={(element) => { labelRefs.current[index] = element }}
            style={{ left: `${node.x / 13.6}%`, top: `${node.y / 5}%` }}
          >
            {node.label}
          </span>
        ))}
      </div>
      <div className="constellation-pointer" />
    </motion.div>
  )
}

export default ConstellationField
