
import { useFrame } from "@react-three/fiber";
import { useMemo, useRef } from "react";
import * as THREE from "three";

type Props = {
  active: boolean;
  speaking?: boolean;
};

const COUNT = 3500;

export default function TomorrowParticles({
  active,
  speaking = false,
}: Props) {
  const points = useRef<THREE.Points>(null);
  const progress = useRef(0);

  const { positions, starts, targets } = useMemo(() => {
    const positions = new Float32Array(COUNT * 3);
    const starts = new Float32Array(COUNT * 3);
    const targets = new Float32Array(COUNT * 3);

    for (let i = 0; i < COUNT; i++) {
      const j = i * 3;

      // Particles start scattered
      starts[j] = (Math.random() - 0.5) * 8;
      starts[j + 1] = (Math.random() - 0.5) * 5;
      starts[j + 2] = (Math.random() - 0.5) * 4;

      // Evenly distribute particles on a sphere
      const y = 1 - (i / (COUNT - 1)) * 2;
      const radius = Math.sqrt(1 - y * y);
      const angle = i * Math.PI * (3 - Math.sqrt(5));

      targets[j] = Math.cos(angle) * radius * 1.12;
      targets[j + 1] = y * 1.12;
      targets[j + 2] = Math.sin(angle) * radius * 1.12;

      positions[j] = starts[j];
      positions[j + 1] = starts[j + 1];
      positions[j + 2] = starts[j + 2];
    }

    return { positions, starts, targets };
  }, []);

  useFrame(({ clock }, delta) => {
    const t = clock.elapsedTime;

    progress.current = THREE.MathUtils.damp(
      progress.current,
      active ? 1 : 0,
      2.8,
      delta
    );

    const p = progress.current;

    if (!points.current) return;

    const geometry = points.current.geometry;
    const attribute = geometry.getAttribute(
      "position"
    ) as THREE.BufferAttribute;

    for (let i = 0; i < COUNT; i++) {
      const j = i * 3;

      const turbulence =
        Math.sin(t * 2 + i * 0.1) * 0.025;

      for (let axis = 0; axis < 3; axis++) {
        positions[j + axis] =
          THREE.MathUtils.lerp(
            starts[j + axis],
            targets[j + axis],
            p
          ) + turbulence;
      }
    }

    attribute.needsUpdate = true;

    points.current.rotation.y += delta * 0.12;
    points.current.position.y =
      Math.sin(t * 1.5) * 0.08;

    const pulse = speaking
      ? 1 + Math.sin(t * 12) * 0.07
      : 1;

    points.current.scale.setScalar(pulse);
  });

  return (
    <points ref={points}>
      <bufferGeometry>
        <bufferAttribute
          attach="attributes-position"
          args={[positions, 3]}
        />
      </bufferGeometry>

      <pointsMaterial
        color="#B695F5"
        size={0.035}
        transparent
        opacity={0.9}
        depthWrite={false}
        sizeAttenuation
      />
    </points>
  );
}

