#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2022 Stéphane Caron
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Upkie wheeled biped bending its knees.
"""

import numpy as np

import meshcat_shapes
import pink
from pink import solve_ik
from pink.tasks import BodyTask, PostureTask
from pink.utils import RateLimiter
from pink.visualization import start_meshcat_visualizer

try:
    from robot_descriptions.loaders.pinocchio import load_robot_description
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "Examples need robot_descriptions, "
        "try ``pip install robot_descriptions``"
    )


if __name__ == "__main__":
    robot = load_robot_description("gen2_description", root_joint=None)
    viz = start_meshcat_visualizer(robot)

    end_effector_task = BodyTask(
        "j2s6s200_end_effector",
        position_cost=1.0,  # [cost] / [m]
        orientation_cost=1.0,  # [cost] / [rad]
    )

    posture_task = PostureTask(
        cost=1e-3,  # [cost] / [rad]
    )

    tasks = [end_effector_task, posture_task]

    configuration = pink.apply_configuration(robot, robot.q0)
    for task in tasks:
        task.set_target_from_configuration(configuration)
    viz.display(configuration.q)

    viewer = viz.viewer
    meshcat_shapes.draw_frame(viewer["end_effector_target"], opacity=0.5)
    meshcat_shapes.draw_frame(viewer["end_effector"], opacity=1.0)

    rate = RateLimiter(frequency=200.0)
    dt = rate.period
    t = 0.0  # [s]
    while True:
        # Update task targets
        end_effector_target = end_effector_task.transform_target_to_world
        end_effector_target.translation[1] = 0.1 * np.sin(t)

        # Update visualization frames
        viewer["end_effector_target"].set_transform(end_effector_target.np)
        viewer["end_effector"].set_transform(
            configuration.get_transform_body_to_world(
                end_effector_task.body
            ).np
        )

        # Compute velocity and integrate it into next configuration
        velocity = solve_ik(configuration, tasks, dt)
        q = configuration.integrate(velocity, dt)
        configuration = pink.apply_configuration(robot, q)

        # Visualize result at fixed FPS
        viz.display(q)
        rate.sleep()
        t += dt
