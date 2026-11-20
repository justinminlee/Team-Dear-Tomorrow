
import { Canvas, useFrame } from "@react-three/fiber";
import { useRef } from "react";
import * as THREE from "three";
import TomorrowParticles from "./TomorrowParticles";

type Props = {
  active: boolean;
  speaking?: boolean;
};

function TomorrowCharacter({
  active,
  speaking = false,
}: Props) {
  const character = useRef<THREE.Group>(null);
  const eyes = useRef<THREE.Group>(null);
  const mouth = useRef<THREE.Mesh>(null);
  const material = useRef<THREE.MeshPhysicalMaterial>(null);
  const arrival = useRef(0);

  useFrame(({ clock }, delta) => {
    const t = clock.elapsedTime;

    arrival.current = THREE.MathUtils.damp(
      arrival.current,
      active ? 1 : 0,
      2.8,
      delta
    );

    const p = arrival.current;

    if (character.current) {
      character.current.position.x = (1 - p) * 4;
      character.current.position.y =
        (1 - p) * 1.2 +
        Math.sin(t * 1.5) * 0.08;

      character.current.rotation.z =
        (1 - p) * -0.5 +
        Math.sin(t * 0.8) * 0.035;

      character.current.scale.setScalar(
        0.5 + p * 0.5
      );
    }

    if (eyes.current) {
      const blink = Math.pow(
        Math.max(0, Math.sin(t * 1.7)),
        80
      );

      eyes.current.scale.y = 1 - blink * 0.9;
    }

    if (mouth.current) {
      mouth.current.scale.y = speaking
        ? 1 + Math.abs(Math.sin(t * 10)) * 2
        : 1;
    }

    if (material.current) {
      material.current.opacity = p;
    }
  });

  return (
    <group ref={character}>
      <mesh>
        <sphereGeometry args={[1.05, 64, 64]} />
        <meshPhysicalMaterial
          ref={material}
          color="#C6A9F5"
          transparent
          opacity={0}
          roughness={0.2}
          metalness={0.08}
          clearcoat={1}
        />
      </mesh>

      <group ref={eyes} position={[0, 0, 0.1]}>
        {[-0.34, 0.34].map((x) => (
          <mesh
            key={x}
            position={[x, 0.18, 0.98]}
            scale={[1, 1.3, 0.6]}
          >
            <sphereGeometry args={[0.105, 24, 24]} />
            <meshStandardMaterial color="#292039" />
          </mesh>
        ))}
      </group>

      <mesh ref={mouth} position={[0, -0.3, 1.04]}>
        <sphereGeometry args={[0.13, 0.055, 0.025, 24, 16]} />
        <meshStandardMaterial color="#714B89" />
      </mesh>
    </group>
  );
}

export default function Tomorrow({
  active,
  speaking = false,
}: Props) {
  return (
    <div className="tomorrow-canvas">
      <Canvas
        camera={{
            position: [0, 0, 4],
            fov: 45,
        }}
        dpr={[1, 2]}
    >
        <ambientLight intensity={1.8} />
        <directionalLight
          position={[3, 5, 5]}
          intensity={2.5}
        />
        <pointLight
          position={[-3, -2, 3]}
          intensity={2}
          color="#B79AFF"
        />

        <group scale={1.15}>
        <TomorrowParticles
            active={active}
            speaking={speaking}
        />

        <TomorrowCharacter
            active={active}
            speaking={speaking}
        />
        </group>
      </Canvas>
    </div>
  );
}
