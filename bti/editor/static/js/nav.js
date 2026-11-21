// Navigation seam between the views and the shell (avoids circular imports). The shell installs the handler.
let handler = null;
export const setNavigator = (fn) => { handler = fn; };
/** Go to a hash route, e.g. go('#/project/x/edit'). Asks about unsaved work first; the same hash reloads the view. */
export const go = (hash) => (handler ? handler(hash) : Promise.resolve(void (location.hash = hash)));
