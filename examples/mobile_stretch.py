#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright 2022 Stéphane Caron
# Copyright 2023 Inria
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

"""Move a Stretch RE1 with a fixed fingertip target around the origin."""

import numpy as np
import pinocchio as pin
import qpsolvers
from loop_rate_limiters import RateLimiter

import meshcat_shapes
import pink
from pink import solve_ik
from pink.tasks import FrameTask
from pink.visualization import start_meshcat_visualizer

try:
    from robot_descriptions.loaders.pinocchio import load_robot_description
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "Examples need robot_descriptions, "
        "try ``pip install robot_descriptions``"
    )

# Trajectory parameters to play with ;)
circle_radius = 0.5  # [m]
fingertip_height = 0.7  # [m]

if __name__ == "__main__":
    robot = load_robot_description(
        "stretch_description", root_joint=pin.JointModelPlanar()
    )
    # __import__("IPython").embed()

    # Initialize visualizer
    viz = start_meshcat_visualizer(robot)
    viewer = viz.viewer
    meshcat_shapes.frame(viewer["base_target_frame"], opacity=0.5)
    meshcat_shapes.frame(viewer["fingertip_target_frame"], opacity=1.0)

    # Define tasks
    base_task = FrameTask(
        "base_link",
        position_cost=0.1,  # [cost] / [m]
        orientation_cost=1.0,  # [cost] / [rad]
    )
    fingertip_task = FrameTask(
        "link_gripper_fingertip_right",
        position_cost=1.0,
        orientation_cost=1e-4,
    )
    tasks = [base_task, fingertip_task]

    # Initialize tasks from the initial configuration
    configuration = pink.Configuration(robot.model, robot.data, robot.q0)
    base_task.set_target_from_configuration(configuration)
    transform_fingertip_target_to_world = pin.SE3(
        rotation=np.eye(3), translation=np.array([0.0, 0.0, fingertip_height])
    ) * configuration.get_transform_frame_to_world(fingertip_task.body)
    center_translation = transform_fingertip_target_to_world.translation[:2]
    fingertip_task.set_target(transform_fingertip_target_to_world)
    viz.display(configuration.q)

    # Select QP solver
    solver = qpsolvers.available_solvers[0]
    if "quadprog" in qpsolvers.available_solvers:
        solver = "quadprog"

    rate = RateLimiter(frequency=100.0)
    dt = rate.period
    t = 0.0  # [s]
    while True:
        # Update task targets
        T = base_task.transform_target_to_world
        u = np.array([np.cos(t), np.sin(t)])
        T.translation[:2] = center_translation + circle_radius * u
        T.rotation = pin.utils.rpyToMatrix(0.0, 0.0, 0.5 * np.pi * t)

        # Update visualizer frames
        viewer["base_target_frame"].set_transform(T.np)
        viewer["fingertip_target_frame"].set_transform(
            fingertip_task.transform_target_to_world.np
        )
        viewer["base_frame"].set_transform(
            configuration.get_transform_frame_to_world(base_task.body).np
        )
        viewer["fingertip_frame"].set_transform(
            configuration.get_transform_frame_to_world(fingertip_task.body).np
        )

        # Compute velocity and integrate it into next configuration
        velocity = solve_ik(configuration, tasks, dt, solver=solver)
        configuration.integrate_inplace(velocity, dt)

        # Visualize result at fixed FPS
        viz.display(configuration.q)
        rate.sleep()
        t += dt
