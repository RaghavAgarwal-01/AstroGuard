import { Suspense } from 'react'
import { Canvas, useLoader } from '@react-three/fiber'
import { OrbitControls, Stars, Line } from '@react-three/drei'
import { TextureLoader } from 'three'

function latLonToVec3(lat, lon, alt_km) {
  const R = 1 + alt_km / 6371
  const phi = (90 - lat) * (Math.PI / 180)
  const theta = (lon + 180) * (Math.PI / 180)
  return [
    -R * Math.sin(phi) * Math.cos(theta),
     R * Math.cos(phi),
     R * Math.sin(phi) * Math.sin(theta)
  ]
}

function Earth() {
  const earthTexture = useLoader(TextureLoader, '/earth.jpg')
  return (
    <mesh>
      <sphereGeometry args={[1, 64, 64]} />
      <meshStandardMaterial map={earthTexture} />
    </mesh>
  )
}

function EarthFallback() {
  return (
    <mesh>
      <sphereGeometry args={[1, 64, 64]} />
      <meshStandardMaterial color="#1a3a5c" />
    </mesh>
  )
}

function Satellite({ satellite, isConjunction, isSelected, onClick }) {
  const pos = latLonToVec3(satellite.lat, satellite.lon, satellite.alt_km)
  const color = isConjunction ? '#ff4444' : '#ffffff'
  const size = isConjunction ? 0.018 : 0.010

  return (
    <mesh position={pos} onClick={() => onClick && onClick(satellite)}>
      <sphereGeometry args={[size, 8, 8]} />
      <meshBasicMaterial color={color} />
    </mesh>
  )
}

export default function Globe({ satellites = [], events = [], selectedEvent = null, onSatClick }) {
  const conjunctionNames = selectedEvent
    ? [selectedEvent.obj_a, selectedEvent.obj_b]
    : events.flatMap(e => [e.obj_a, e.obj_b])

  const selectedPair = selectedEvent
    ? satellites.filter(s => [selectedEvent.obj_a, selectedEvent.obj_b].includes(s.name))
    : []

  return (
    <Canvas
      camera={{ position: [0, 0, 3], fov: 45 }}
      style={{ background: '#0a0a1a', width: '100%', height: '100%' }}
    >
      <ambientLight intensity={0.3} />
      <directionalLight position={[5, 3, 5]} intensity={1.2} />
      <Stars radius={100} depth={50} count={3000} factor={4} saturation={0} />

      <Suspense fallback={<EarthFallback />}>
        <Earth />
      </Suspense>

      {satellites.map(sat => (
        <Satellite
          key={sat.name}
          satellite={sat}
          isConjunction={conjunctionNames.includes(sat.name)}
          isSelected={selectedEvent && [selectedEvent.obj_a, selectedEvent.obj_b].includes(sat.name)}
          onClick={onSatClick}
        />
      ))}

      {selectedPair.length === 2 && (
        <Line
          points={[
            latLonToVec3(selectedPair[0].lat, selectedPair[0].lon, selectedPair[0].alt_km),
            latLonToVec3(selectedPair[1].lat, selectedPair[1].lon, selectedPair[1].alt_km),
          ]}
          color="#ff4444"
          lineWidth={1.5}
          dashed
        />
      )}

      <OrbitControls enableZoom={true} enablePan={false} autoRotate={true} autoRotateSpeed={0.4} />
    </Canvas>
  )
}