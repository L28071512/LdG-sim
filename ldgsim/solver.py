import numpy as np

from ldgsim import utility as u
from ldgsim import param as p
from ldgsim import cond as c
from ldgsim import mesh as m


""" transform n and S into Q """

def Q_tensor(n, S=1, P=0):
	''' calculate the Q tensor of a certain position which evalueates the liquid crystal molecule's orientation, degree of order and biaxiality '''
	Q = np.zeros((3, 3))
	for row in range(3):
		for col in range(3):
			if row == col:
				Q[row, col] = (3 * n[row] * n[col] - 1) * (S / 2)
			else:
				Q[row, col] = (3 * n[row] * n[col] - 0) * (S / 2)
	return Q

# TODO: DUBUG
def printQ(Q):
    for i in Q:
        for j in i:
            print(j, end=' ')
        print()

def all_Q(mesh):
    for layer in mesh:
        for line in layer:
            for grid in line:
                Q = Q_tensor(grid.n, grid.S, grid.P)
                printQ(Q)
                grid.Q = Q

# deprecated
def tensor_Q(n, S=1, P=0):
	''' calculate the Q tensor of a certain position which evalueates the liquid crystal molecule's orientation, degree of order and biaxiality '''
	n = np.array(n)
	Q = (np.outer(n, n) * 3 - np.eye(3)) * (S / 2)
	Q -= np.trace(Q) * np.eye(3) / 3
	return Q

""" solve n and S field from Q """

def eigen(grid):
    ''' find the max eigenvalue and the corresponding normalized eigvector of Q '''
    eig_values, eig_vectors = np.linalg.eig(grid.Q)
    S = np.amax(eig_values)
    n = eig_vectors[:, np.where(eig_values == np.amax(eig_values)[0][0])]
    grid.S = S
    grid.n = n
    return S, n
Eigen = np.vectorize(eigen)

""" iteration """

# deprecated
def retrive_Q(mesh):
    ''' retrive the tensorial order parameter Q from mesh and store it as a big 3*3 tuple '''
    all_Q = np.vectorize(lambda grid, i, j: grid.Q[i, j])
    Qs = np.empty((3, 3))
    for i in range(3):
        for j in range(3):
            Qs[i, j] = all_Q(mesh, i, j)
    return Qs   # shape = (3, 3, 27, 27, 17)

# deprecated
def laplace(Qs, i, j):
    ''' finite difference discrete laplacian of Q_ij of all the points in the mesh '''
    lap_Q = np.empty((p.x_nog, p.y_nog, p.z_nog))
    for x in range(p.x_nog):
        for y in range(p.y_nog):
            for z in range(p.z_nog):
                lap_Q[x, y, z] = np.average(Qs[i, j, x-1, y, z],
                                            Qs[i, j, x+1, y, z],
                                            Qs[i, j, x, y-1, z],
                                            Qs[i, j, x, y+1, z],
                                            Qs[i, j, x, y, z-1],
                                            Qs[i, j, x, y, z+1]) - Qs[i, j, x, y, z]
    return lap_Q   # shape = (27, 27, 17)

# deprecated
def normal_dot_gradient(Qs, i, j, dr=p.dr_lap):
    ''' inner product of gradient of Q_ij and the surface normal of all the points in the mesh '''
    # surface normal = normalized r field (shape = 27 * 27 * 17)
    grad_Q = np.empty((p.x_nog, p.y_nog, p.z_nog))
    for x in range(p.x_nog):
        for y in range(p.y_nog):
            for z in range(p.z_nog):
                normal = np.array((x, y, z)) / np.linalg.norm(normal)
                grad_Q[x, y, z] = sum(normal[0] * (Qs[i, j, x, y, z] - Qs[i, j, x-1, y, z]) / dr,
                                     normal[1] * (Qs[i, j, x, y, z] - Qs[i, j, x, y-1, z]) / dr,
                                     normal[2] * (Qs[i, j, x, y, z] - Qs[i, j, x, y, z-1]) / dr)
    return grad_Q   # shape = (27, 27, 17)

def laplacian(mesh):
    ''' finite difference discrete laplacian of Q_ij of all the points in the mesh '''
    lap_Qs = np.empty(mesh.shape)
    for x in range(p.x_nog):
        for y in range(p.y_nog):
            for z in range(p.z_nog):
                lap_Qs[x, y, z] = np.average(mesh[x-1, y, z].Q,
                                             mesh[x+1, y, z].Q,
                                             mesh[x, y-1, z].Q,
                                             mesh[x, y+1, z].Q,
                                             mesh[x, y, z-1].Q,
                                             mesh[x, y, z+1].Q) - mesh[x, y, z].Q
    return lap_Qs    # shape = (27, 27, 17, 3, 3)

def gradient(mesh, dx=p.dr_lap, dy=p.dr_lap, dz=p.dr_lap):
    '''gradient of Q_ij of all the points in the mesh '''
    grad_Qs = np.empty(mesh.shape)
    for x in range(p.x_nog):
        for y in range(p.y_nog):
            for z in range(p.z_nog):
                grad_Qs[x, y, z] = np.array([(mesh[x, y, z].Q - mesh[x-1, y, z].Q) / dx,
                                             (mesh[x, y, z].Q - mesh[x, y-1, z].Q) / dy,
                                             (mesh[x, y, z].Q - mesh[x, y, z-1].Q) / dz])
    return grad_Qs   # shape = (27, 27, 17, 3, 3, 3)

def h_bulk(Q, lap_Q, L=p.L, A=p.A, B=p.B, C=p.C):
    ''' solve the molecular field on the bulk area '''
    h = np.empty((3, 3))
    for i in range(3):
        for j in range(3):
            h[i, j] = (L * lap_Q[i, j] -
                       A * Q[i, j] -
                       B * np.sum(np.multiply(Q[i], Q.T[j])) -
                       C * Q[i, j] * np.sum(np.multiply(Q, Q.T)))
    return h

def h_surf(Q, grad_Q, Q_bound, surf_normal, W=p.W_sub, L=p.L):
    ''' solve the molecular field on the surface of substrate or sphere '''
    h = np.empty((3, 3))
    for i in range(3):
        for j in range(3):
            h[i, j] = (L * np.sum(np.multiply(grad_Q, surf_normal), axis=0) +
                       W * (Q[i, j] - Q_bound[i, j]))
    return h

def evolute(mesh, L=p.L, A=p.A, B=p.B, C=p.C, W_subs=p.W_sub, W_shel=p.W_she, dt=p.dt, gamma=p.gamma):
    lap_Qs = laplacian(mesh)
    grad_Qs = gradient(mesh)

    for x in range(p.x_nog):
        for y in range(p.y_nog):
            for z in range(p.z_nog):
                grid = mesh[x, y, z]
                lap_Q = lap_Qs[x, y, z]
                grad_Q = grad_Qs[x, y, z]

                if c.is_top(grid) or c.is_bot(grid):        # h_surf of substrate
                    Q_bound = Q_tensor(p.n_subs, p.S_subs)
                    grid.h = h_surf(grid.Q, grad_Q, Q_bound=Q_bound, surf_normal=np.array([0, 0, 1]), W=W_subs)
                elif c.is_osh(grid) or c.is_ish(grid):      # h_surf of shell
                    Q_bound = Q_tensor(c.envelope(p.n_shel), p.S_subs)
                    grid.h = h_surf(grid.Q, grad_Q, Q_bound=Q_bound, surf_normal=u.cartesian(grid.r), W=W_shel)
                else:                                       # h_bulk
                    grid.h = h_bulk(grid.Q, lap_Q)
                grid.Q += grid.h * dt / gamma - np.trace(grid.Q) * np.eye(3) / 3     # EL modification

if __name__ == "__main__":
    a = np.arange(1, 28).reshape([3, 3, 3])
    print(a)
    b = np.array([1, 2, 3])
    print(b)
    c = np.sum(np.multiply(a, b), axis=0)
    print(c)

# TODO: XZ-periodic boundary

'''
# XZ-periodic boundary

F_bulk = 
F_subs = 
F_shel = 
F_total = F_bulk + F_subs + F_shel

'''