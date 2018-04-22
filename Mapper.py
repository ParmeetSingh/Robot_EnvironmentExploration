
from util import Util as util
import math
import time
import csv
import numpy as np
from ev3dev.ev3 import *

class Mapping:

    def __init__(self, Move):
        
        '''MAKE SURE THE SENSOR IS POINTED FORWARD AT START OF CODE (on-robot jig needs to be designed to do this)'''
        self.mS = MediumMotor('outD')  # mS = motor_sensor for the ultrasonic sensor to be rotated
        self.ultra1 = UltrasonicSensor()
        self.sensor_range = 100
        self.gear_ratio = -28  # Motor must turn 28 times for 1 turn of sensor

        self.mS.position = 0  # The sensor is zeroed with relation to the robot, which starts at pi/2 degrees global.

        '''The width of the robot'''
        self.width = Move.axle_length + 2

        '''Angle resolution for scanning, in degrees'''
        self.scan_res = 10
        self.N_theta = int(360/self.scan_res)
        self.max_range = 255.0
        '''Initial Conditions, render a space'''
        maxX, maxY = (110, 140)  # Space is 103.0, 87.5 cm, so the rendered area is a bot larger to forgive misalignment

        minX = -maxX
        minY = -maxY

        res = 5  # cm
        numX = int((maxX - minX) / res)
        numY = int((maxY - minY) / res)

        self.X = np.linspace(minX, maxX, numX)
        self.Y = np.linspace(minY, maxY, numY)
        self.XX, self.YY = np.meshgrid(self.X, self.Y)

        '''A matrix containing all the grid points in the rendered space, an occupancy grid, , for an obstacle probability to 
           be assigned'''
        self.ZZ = np.zeros_like(self.XX)

        '''Threshold for obstacle detection'''
        self.obs_threshold = 0.5

        self.sensor_model_variance = 25
        self.resolution = res
        self.minX = minX
        self.minY = minY
        self.maxX = maxX
        self.maxY = maxY

    def coord_to_index(self, x, y):
        """
        Take in the meshgrid XX and YY matrixes, and a point of interest. Return the closest coordinate on the meshgrid in
        terms of meshgrid indices.

        :param x: float
        :param y: float
        :return:
        """
        idxX = np.argmin(np.abs(self.X - x))
        idxY = np.argmin(np.abs(self.Y - y))

        return idxX, idxY

    def test_index(self, y, x):
        """
        test an occupancy grid mesh point to see if there is an obstacle there or not, based off of the threshold value set
        in the initial conditions.

        :param y: float, the x-axis coordinate on the meshgrid (meshgrids transpose direction with their indexes)
        :param x: float, the y-axis coordinate on the meshgrid (meshgrids transpose direction with their indexes)
        :return: obstruction: bool, if the x,y point is an obstacle above threshold
        :return: ZZ(x,y): float, the probability there is an obstacle at the given coordinate
        """
        if self.ZZ[x][y] > self.obs_threshold:
            obstruction = True
        else:
            obstruction = False

        return obstruction

    def check_path(self, x1, y1, x2, y2):
        """
        Check if the path the robot intends to drive along is clear of obstacles.

        Method:
        Draw three lines along the robots path and check if they collide with any of the objects on the occupancy grid

        :param move: The movement object
        :param x1: start x
        :param y1: start y
        :param x2: goal x
        :param y2: goal y
        :return: path_clear: bool, is the path clear or not?
        """

        theta = math.atan2(y2-y1, x2-x1)
        length = math.sqrt((x2-x1)**2 + (y2-y1)**2)
        
        N = math.ceil(length/(3.0*self.resolution))  # Ensure the resolution of the lines is much smaller than the grid to avoid gaps
        #print("N is",N,x1,x2,y1,y2)
        if (N==0):
            print("N is 0")
            return True

        middle_line_x = np.linspace(x1, x2, N)
        middle_line_y = np.linspace(y1, y2, N)


        '''Left line points'''
        x1l = x1 + self.width / 2 * math.cos(theta + math.pi)
        x2l = x2 + self.width / 2 * math.cos(theta + math.pi)
        y1l = y1 + self.width / 2 * math.sin(theta + math.pi)
        y2l = y2 + self.width / 2 * math.sin(theta + math.pi)

        left_line_x = np.linspace(x1l, x2l, N)
        left_line_y = np.linspace(y1l, y2l, N)

        '''Right line points'''
        x1r = x1 + self.width / 2 * math.cos(theta - math.pi)
        x2r = x2 + self.width / 2 * math.cos(theta - math.pi)
        y1r = y1 + self.width / 2 * math.sin(theta - math.pi)
        y2r = y2 + self.width / 2 * math.sin(theta - math.pi)

        right_line_x = np.linspace(x1r, x2r, N)
        right_line_y = np.linspace(y1r, y2r, N)

        path_clear = []
        #print("Middle Line",middle_line_x, N)

        '''In this section, the code will check each point along the lines and return 1 or zero if it is over a'''
        '''threshold value. It will then store this to an array, and then take the average of the three lines to find'''
        '''the percent chance it is going to make it. If the chance is good (ie over 95%), it will go for the goal'''

        path_clear_m = []
        path_clear_l = []
        path_clear_r = []

        for idx in range(len(middle_line_x)):
            x, y = self.coord_to_index(middle_line_x[idx], middle_line_y[idx])
            if self.test_index(x, y):
                path_clear_m[idx] = 0
            else:
                path_clear_m[idx] = 1
            x, y = self.coord_to_index(left_line_x[idx], left_line_y[idx])
            if self.test_index(x, y):
                path_clear_l[idx] = 0
            else:
                path_clear_l[idx] = 1
            x, y = self.coord_to_index(right_line_x[idx], right_line_y[idx])
            if self.test_index(x, y):
                path_clear_r[idx] = 0
            else:
                path_clear_r[idx] = 1

        path_clear_m = np.array(path_clear_m)
        path_clear_l = np.array(path_clear_l)
        path_clear_r = np.array(path_clear_r)

        percent_clear = np.mean([np.mean(path_clear_m), np.mean(path_clear_l), np.mean(path_clear_r)])  # from 0 to 1

        if percent_clear >= 0.95:
            path_clear = True
        else:
            path_clear = False

        # for idx in range(len(middle_line_x)):
        #     x,y = self.coord_to_index(middle_line_x[idx], middle_line_y[idx])
        #     if self.test_index(x,y):
        #         path_clear = False
        #         print('Cannot complete direct line to goal - Object in way - Centre line')
        #         break
        #     x,y = self.coord_to_index(left_line_x[idx], left_line_y[idx])
        #     if self.test_index(x,y):
        #         path_clear = False
        #         print('Cannot complete direct line to goal - Object in way - Left side')
        #         break
        #     x,y = self.coord_to_index(right_line_x[idx], right_line_y[idx])
        #     if self.test_index(x,y):
        #         path_clear = False
        #         print('Cannot complete direct line to goal - Object in way - Right side')
        #         break
        #
        #     path_clear = True

        return path_clear

    def update_occupancy_grid(self, robot_x, robot_y, polar_length, polar_angle):
        """
        Update the ZZ occupancy grid such that it may be used for mapping and path planning.

        :param robot_x: float, the x position of the robot in inches
        :param robot_y: float, the y position of the robot in inches
        :param polar_length: array, the length of each ultrasonic pulse from the robot in the update method
        :param polar_angle: array, the global angle that each polar_length element was recorded at.
        :return:
        """
        
        print('--Updateing occupancy grid...---') 
        for idx, ray in enumerate(polar_length):
            
            # Play a sound so you don't get bored as it updates
            Sound.tone(100*polar_angle[idx]/40, 30)  # Frequency [Hz], duration [ms]
            
            x_ray = robot_x + ray * math.cos(math.radians(polar_angle[idx]))  # cartesian components of the ray
            y_ray = robot_y + ray * math.sin(math.radians(polar_angle[idx]))

            #x_idx, y_idx = self.coord_to_index(x_ray, y_ray)
            #print('Ray end point: ',x_ray,y_ray,'Index: ',x_idx,y_idx) 	
            #self.ZZ[y_idx][x_idx] = 1  # TODO: This is a great place to implement a sensor model.
            self.update_grid_point(x_ray,y_ray) # updating the grid points values according to a gaussian model

        Sound.tone(921, 200)
        '''Normalize the meshgrid'''
        

        # Write to file so that the meshgrid may be viewed to pass the project.
        # COMMAND:
        # scp robot@ev3dev.local:~/Robot_EnvironmentExploration/occupancy_grid.csv /Users/Jack/Documents/DAL/MECH6905/Capstone
        with open("occupancy_grid.csv", "w") as f:
            writer = csv.writer(f)
            writer.writerows(self.ZZ)

    def update(self,move):
        """
        Turn the ultrasonic sensor to zero degrees global, and then scan 360 degrees, send the results to get updated in
        the occupancy grid.

        :return:
        """
        #print('Updating world map...')

        '''Turn motor to zero degrees in global coordinate'''
        robot_x, robot_y, robot_phi = move.pose()

        # No intelligent script to optimize angle to avoid wrapping the cord of the sensor
        sensor_desired_position = math.degrees(-robot_phi)
        #print('Robot thinks sensor should turn: ',sensor_desired_position,' degrees to zero')
        motor_desired_position = int(sensor_desired_position*self.gear_ratio)
        self.mS.run_to_abs_pos(position_sp=motor_desired_position, speed_sp=1500, stop_action='hold')

        polar_length = []
        polar_angle = []

        sensor_theta = util.frange(0, 360, self.scan_res)
        for idx, theta in enumerate(sensor_theta):

            self.mS.run_to_abs_pos(position_sp=(theta*self.gear_ratio+motor_desired_position), stop_action='hold')
            self.mS.wait_while('running')
            length = self.ultra1.distance_centimeters
            #if length >= self.max_range:
            #    length = 5*self.max_range  # Make the measurement inf incase the sensor doesn't read in range
            polar_length.append(length)
            polar_angle.append(theta)

        '''Turn sensor back to zero so the cord doesn't wrap'''
        self.mS.run_to_abs_pos(position_sp=0, speed_sp=1500, stop_action='hold')

        '''Send measurements for processing'''
        self.update_occupancy_grid(robot_x, robot_y, polar_length, polar_angle)
        #print(polar_length)
        '''Return 360 dict to exploration'''
        return dict(zip(polar_angle, polar_length))


    def update_grid_point(self, mu_x, mu_y):
        """
        Update the occupancy grid with a level of uncertainty around where each point was detected

        :param mux:
        :param muy:
        :return:
        """
        sigma = self.sensor_model_variance
        weight = 2000
        cm_x = 20  # How many centimeters in the x or y direction to apply the gaussian to
        cm_y = 20
        Nx = (cm_x)/self.resolution + 1
        Ny = (cm_y)/self.resolution + 1

        for x in np.linspace(mu_x - cm_x/2, mu_x + cm_x/2, Nx):
            for y in np.linspace(mu_y - cm_y/2, mu_y + cm_y/2, Ny):
                x_idx, y_idx = self.coord_to_index(x, y)
                # print("Writing bump to: [", x_idx, ", ", y_idx, "]")
                self.ZZ[y_idx][x_idx] = self.ZZ[y_idx][x_idx] + weight*(1 / (2 * math.pi * sigma ** 2)) * np.exp(
                    -1 * (((x - mu_x) ** 2) + ((y - mu_y) ** 2) / (2 * sigma ** 2)))


    def update_grid_bump(self, x_line, y_line):
        """
        Update with a gaussian distribution the area along the bumper where an object has been hit. Called by the move fn

        :param x_line: list, the x-values of the bumper line
        :param y_line: list, the y-values of the bumper line
        :return:
        """
        sigma = 4  # Variance of bump sensor in cm
        weight = 50
        cm_x = 10
        cm_y = 10
        Nx = (cm_x)/self.resolution + 1
        Ny = (cm_y)/self.resolution + 1

        print("Updating grid with bump")
        print("Updating this many elements for bump", len(x_line)*11**2)
        for idx,num in enumerate(x_line):
            mu_x = x_line[idx]
            mu_y = y_line[idx]

            for x in np.linspace(mu_x - cm_x/2, mu_x + cm_x/2, Nx):
                for y in np.linspace(mu_y - cm_y/2, mu_y + cm_y/2, Ny):
                    x_idx, y_idx = self.coord_to_index(x, y)
                    #print("Writing bump to: [", x_idx, ", ", y_idx, "]")
                    self.ZZ[y_idx][x_idx] = self.ZZ[y_idx][x_idx] + weight*(1 / (2 * math.pi * sigma ** 2)) * np.exp(-1 * (((x - mu_x)**2) + ((y - mu_y)**2) / (2 * sigma ** 2)))

