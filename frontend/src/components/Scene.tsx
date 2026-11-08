import { Component, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js'
import type { Point, SegmentKey } from '../lib/api'

const SCALE = 3.25
const MATERIALS: Record<SegmentKey, THREE.MeshPhysicalMaterialParameters> = {
  vip: { color: '#4a2212', roughness: .16, metalness: 0, clearcoat: 1, clearcoatRoughness: .05 },
  regular: { color: '#b84f20', roughness: .22, metalness: 1 },
  deal: { color: '#ecdcc4', roughness: .26, metalness: 0, clearcoat: 1 },
  new: { color: '#d69a4c', roughness: .2, metalness: 1 },
}

function Env() {
  const { gl, scene } = useThree()
  useEffect(() => {
    const pm = new THREE.PMREMGenerator(gl); const rt = pm.fromScene(new RoomEnvironment(), .04)
    scene.environment = rt.texture; scene.environmentIntensity = .9
    return () => { rt.dispose(); pm.dispose() }
  }, [gl, scene])
  return null
}

function Beads({ points, k, focus, onHover }: { points: Point[]; k: SegmentKey; focus: SegmentKey | null; onHover: (p: Point | null, e?: PointerEvent) => void }) {
  const ref = useRef<THREE.InstancedMesh>(null!)
  const mat = useMemo(() => new THREE.MeshPhysicalMaterial(MATERIALS[k]), [k])
  const visible = !focus || focus === k
  useLayoutEffect(() => {
    const m = new THREE.Matrix4()
    points.forEach((p, i) => {
      const r = (.05 + .017 * Math.min(4.6, Math.log10(p.spend + 1))) * (visible ? 1 : .4)
      m.makeScale(r, r, r).setPosition(p.x * SCALE, p.y * SCALE, p.z * SCALE)
      ref.current.setMatrixAt(i, m)
    })
    ref.current.instanceMatrix.needsUpdate = true
    ref.current.computeBoundingSphere()
  }, [points, visible])
  useEffect(() => { mat.transparent = !visible; mat.opacity = visible ? 1 : .22; mat.needsUpdate = true }, [visible, mat])
  return (
    <instancedMesh ref={ref} args={[undefined, mat, points.length]} key={points.length}
      onPointerMove={e => { e.stopPropagation(); if (e.instanceId !== undefined) onHover(points[e.instanceId], e.nativeEvent) }}
      onPointerOut={() => onHover(null)}>
      <sphereGeometry args={[1, 16, 12]} />
    </instancedMesh>
  )
}

function Frame() {
  const geo = useMemo(() => new THREE.EdgesGeometry(new THREE.BoxGeometry(8, 8, 8)), [])
  return (
    <group>
      <lineSegments geometry={geo}><lineBasicMaterial color="#d6a376" transparent opacity={.42} /></lineSegments>
      <mesh position={[0, -4.22, 0]}><cylinderGeometry args={[5.6, 5.85, .3, 96]} /><meshPhysicalMaterial color="#6a3a20" metalness={1} roughness={.22} /></mesh>
      <mesh position={[0, -4.04, 0]} rotation={[Math.PI / 2, 0, 0]}><torusGeometry args={[5.2, .02, 12, 160]} /><meshBasicMaterial color="#f0c08e" /></mesh>
    </group>
  )
}

function Marker({ position, color }: { position: [number, number, number]; color: string }) {
  const ref = useRef<THREE.Group>(null!); const halo = useRef<THREE.Mesh>(null!)
  const target = useMemo(() => new THREE.Vector3(), [])
  useFrame(({ clock }, d) => {
    target.set(position[0] * SCALE, position[1] * SCALE, position[2] * SCALE)
    ref.current.position.lerp(target, 1 - Math.exp(-d * 5))
    const s = 1 + .22 * Math.sin(clock.elapsedTime * 2.6); halo.current.scale.setScalar(s)
  })
  return (
    <group ref={ref} position={[0, 6, 0]}>
      <mesh><sphereGeometry args={[.2, 32, 24]} /><meshPhysicalMaterial color="#fff4e2" emissive={color} emissiveIntensity={.9} roughness={.15} clearcoat={1} /></mesh>
      <mesh ref={halo}><sphereGeometry args={[.42, 32, 24]} /><meshBasicMaterial color="#f3d2b0" transparent opacity={.18} depthWrite={false} /></mesh>
    </group>
  )
}

function TouchFix() {
  const { gl } = useThree()
  useEffect(() => { const t = setTimeout(() => { gl.domElement.style.touchAction = 'pan-y' }, 80); return () => clearTimeout(t) }, [gl])
  return null
}

class Boundary extends Component<{ children: ReactNode; fallback: ReactNode }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() { return this.state.failed ? this.props.fallback : this.props.children }
}

export interface SceneProps { points: Point[]; focus?: SegmentKey | null; marker?: { x: number; y: number; z: number; color?: string } | null; currency?: string; names?: Record<string, string> }

export default function Scene({ points, focus = null, marker, currency = '', names = {} }: SceneProps) {
  const [tip, setTip] = useState<{ p: Point; x: number; y: number } | null>(null)
  const box = useRef<HTMLDivElement>(null)
  const groups = useMemo(() => (['vip', 'regular', 'deal', 'new'] as SegmentKey[]).map(k => [k, points.filter(p => p.s === k)] as const), [points])
  const reduced = typeof matchMedia !== 'undefined' && matchMedia('(prefers-reduced-motion: reduce)').matches
  const hover = (p: Point | null, e?: PointerEvent) => {
    if (!p || !e || !box.current) return setTip(null)
    const r = box.current.getBoundingClientRect(); setTip({ p, x: e.clientX - r.left, y: e.clientY - r.top })
  }
  const fallback = <div className="scene-fallback"><img src="/img/hero.jpg" alt="Four customer groups shown as clusters of beads" /></div>
  return (
    <div className="scene" ref={box}>
      <Boundary fallback={fallback}>
        <Canvas camera={{ position: [12.5, 4.6, 15], fov: 36 }} dpr={[1, 1.6]} gl={{ antialias: true, alpha: true }}>
          <Env />
          <directionalLight position={[8, 12, 6]} intensity={2.4} color="#ffe6c8" />
          <directionalLight position={[-9, 3, -8]} intensity={1.3} color="#ffab6b" />
          <group position={[0, .55, 0]}>
            <Frame />
            {groups.map(([k, pts]) => pts.length > 0 && <Beads key={k} k={k} points={pts} focus={focus} onHover={hover} />)}
            {marker && <Marker position={[marker.x, marker.y, marker.z]} color={marker.color ?? '#e9bd92'} />}
          </group>
          <OrbitControls enablePan={false} enableZoom={false} autoRotate={!reduced && !tip} autoRotateSpeed={.55} minPolarAngle={.5} maxPolarAngle={1.75} />
          <TouchFix />
        </Canvas>
      </Boundary>
      {tip && (
        <div className="tip" style={{ left: tip.x, top: tip.y }}>
          <strong>{names[tip.p.s]}</strong>Customer {tip.p.id}<br />{tip.p.orders} orders, {currency}{Math.round(tip.p.spend).toLocaleString('en-GB')}
        </div>
      )}
    </div>
  )
}
